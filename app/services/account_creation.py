"""
Orchestration création compte LeBonCoin.
Workflow WF-01 du plan d'implémentation.

Mode A (principal) : Patchright + proxy 4G iproxy.online
Mode B (fallback)  : browser-use Cloud + IP résidentielle FR
"""
import asyncio
import logging
from dataclasses import dataclass

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import AccountStatus, DatadomeTrustLevel
from app.tables import PlatformAccount

log = logging.getLogger(__name__)
settings = get_settings()


class ProxyUnavailableError(Exception):
    """R07 : proxy 4G indisponible — ne jamais fallback sur IP VPS."""


class AccountCreationError(Exception):
    pass


@dataclass
class CreationResult:
    account_id: str
    email: str
    phone: str
    mode: str  # "A" ou "B"


async def _verify_proxy_is_fr_carrier(proxy: boundaries.ProxyInfo) -> None:
    """
    Vérifie ASN — doit être opérateur télécom FR (pas datacenter).
    R07 : si la vérification échoue → lever ProxyUnavailableError.
    """
    fr_carriers = {"orange", "sfr", "bouygues", "free mobile", "free"}
    asn_lower = proxy.asn_org.lower()
    if proxy.country != "FR" or not any(c in asn_lower for c in fr_carriers):
        raise ProxyUnavailableError(
            f"IP non FR-opérateur : country={proxy.country} asn={proxy.asn_org!r}. "
            "Règle R07 — arrêt de la création."
        )


async def _check_active_pool_needs_account() -> bool:
    """Retourne True si le pool de comptes ACTIFS est sous le minimum (R — 3 comptes)."""
    from sqlalchemy import func, select
    async with get_db() as db:
        result = await db.execute(
            select(func.count()).select_from(PlatformAccount).where(
                PlatformAccount.status.in_([AccountStatus.ACTIF, AccountStatus.EN_CHAUFFE])
            )
        )
        count = result.scalar() or 0
        return count < settings.lbc_accounts_min_active


async def create_lbc_account(mode: str = "A") -> CreationResult:
    """
    Crée un nouveau compte LBC. Appelé par Celery task create_account_task.

    mode="A" : Patchright + iproxy 4G (principal, trust score maximal)
    mode="B" : browser-use Cloud (fallback si iproxy indisponible)
    """
    # 1. Email unique via Mailgun catch-all
    email = boundaries.generate_email()
    log.info("Création compte LBC — email=%s mode=%s", email, mode)

    # 2. Proxy (Mode A uniquement)
    proxy = None
    if mode == "A":
        rotated = await boundaries.rotate_4g_ip()
        if not rotated:
            raise ProxyUnavailableError("rotate_4g_ip() a échoué — iproxy.online indisponible.")
        await asyncio.sleep(35)  # délai post-rotation IP (règle : 30–60s)
        proxy = await boundaries.get_4g_proxy()
        await _verify_proxy_is_fr_carrier(proxy)
        log.info("Proxy 4G obtenu : %s | ASN: %s", proxy.url.split("@")[1], proxy.asn_org)

    # 3. Numéro OTP — SmsApp.io
    order = await boundaries.buy_number("france", "leboncoin")
    log.info("OTP acheté : phone=%s id=%s", order.phone, order.id)

    # 4. Navigation LBC + inscription (Patchright ou browser-use)
    # TODO (Sprint 2) : intégration Patchright / browser-use Cloud
    # Pour l'instant : stub retournant l'état attendu pour les tests
    log.info("Navigation LBC — stub actif (Sprint 2 implantera Patchright)")

    # 5. Attendre code SMS OTP
    code = await boundaries.poll_sms(order.id, max_wait=120)
    if code is None:
        await boundaries.cancel_number(order.id)
        raise AccountCreationError(f"Timeout OTP pour order_id={order.id} — remboursement déclenché.")
    log.info("Code OTP reçu : %s", code)

    # 6. TODO (Sprint 2) : soumettre le code OTP dans Patchright
    # 7. TODO (Sprint 2) : attendre email de confirmation Mailgun

    # 8. Persister en DB — statut EN_CHAUFFE
    async with get_db() as db:
        account = PlatformAccount(
            email=email,
            phone_otp=order.phone,
            status=AccountStatus.EN_CHAUFFE,
            datadome_trust_level=DatadomeTrustLevel.LOW,
            quota_actuel=10,
        )
        db.add(account)
        await db.flush()
        account_id = str(account.id)

    log.info("Compte créé : id=%s statut=EN_CHAUFFE warm-up 48–72h", account_id)
    return CreationResult(account_id=account_id, email=email, phone=order.phone, mode=mode)
