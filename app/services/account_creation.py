"""
Orchestration création compte LeBonCoin.
Workflow WF-01 du plan d'implémentation.

Mode A (principal) : Patchright + proxy 4G iproxy.online
Mode B (fallback)  : browser-use Cloud + IP résidentielle FR
"""
import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app import boundaries
from app.config import get_settings
from app.db import get_db
from app.models import AccountStatus, DatadomeTrustLevel
from app.tables import PlatformAccount

log = logging.getLogger(__name__)
settings = get_settings()

_LBC_SIGNUP_URL = "https://www.leboncoin.fr/create_user/account"
_EMAIL_CODE_TIMEOUT = 300   # secondes max pour validation email
_BTN_RE = re.compile(r"(continuer|suivant|créer|s['']inscrire|valider|confirmer)", re.I)


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
    fr_carriers = {"orange", "sfr", "bouygues", "free mobile", "free"}
    asn_lower = proxy.asn_org.lower()
    if proxy.country != "FR" or not any(c in asn_lower for c in fr_carriers):
        raise ProxyUnavailableError(
            f"IP non FR-opérateur : country={proxy.country} asn={proxy.asn_org!r}. "
            "Règle R07 — arrêt de la création."
        )


async def _check_active_pool_needs_account() -> bool:
    from sqlalchemy import func, select
    async with get_db() as db:
        result = await db.execute(
            select(func.count()).select_from(PlatformAccount).where(
                PlatformAccount.status.in_([AccountStatus.ACTIF, AccountStatus.EN_CHAUFFE])
            )
        )
        count = result.scalar() or 0
        return count < settings.lbc_accounts_min_active


def _session_path_for(account_id: str) -> str:
    """Retourne le dossier de session Patchright pour un compte donné."""
    path = Path(settings.sessions_dir) / account_id
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _build_proxy_config(proxy: boundaries.ProxyInfo) -> dict:
    """
    Convertit ProxyInfo en dict Playwright.
    Format ProxyInfo.url : http://user:pass@host:port
    """
    parsed = urlparse(proxy.url)
    cfg: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        cfg["username"] = parsed.username
        cfg["password"] = parsed.password or ""
    return cfg


async def _poll_email_code_redis(email: str, timeout: int = _EMAIL_CODE_TIMEOUT) -> str | None:
    """
    Poll Redis toutes les 2s jusqu'à réception du code email LBC.
    La clé est positionnée par webhooks/email.py quand Mailgun livre.
    """
    import redis.asyncio as aioredis

    redis_key = f"email_code:{email}"
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    try:
        while loop.time() < deadline:
            code = await client.get(redis_key)
            if code:
                await client.delete(redis_key)
                return code
            await asyncio.sleep(2)
    finally:
        await client.aclose()
    return None


async def _create_with_patchright(
    email: str,
    proxy: boundaries.ProxyInfo,
    session_path: str,
    otp_order_id: str,
) -> None:
    """
    Flux de création compte LBC via Patchright (Mode A).

    Séquence :
      1. Ouvre LBC inscription avec proxy 4G
      2. Remplit le formulaire (email + mot de passe)
      3. Valide le code OTP SMS (poll SmsApp.io)
      4. Valide le code email si LBC l'exige (poll Redis ← webhook Mailgun)
      5. Maintient le contexte persistant dans session_path
    """
    from patchright.async_api import async_playwright

    async with async_playwright() as p:
        # Contexte persistant recommandé par docs Patchright pour le stealth.
        # Ne pas ajouter user_agent ni headers custom (anti-fingerprint).
        ctx = await p.chromium.launch_persistent_context(
            session_path,
            headless=True,
            focus_control=False,
            proxy=_build_proxy_config(proxy),
        )
        try:
            page = await ctx.new_page()

            # ── 1. Navigation inscription ────────────────────────────────────
            await page.goto(_LBC_SIGNUP_URL, wait_until="networkidle", timeout=30_000)
            log.info("Patchright : page inscription LBC chargée")

            # ── 2. Remplissage formulaire ────────────────────────────────────
            await page.get_by_label(re.compile(r"email", re.I)).fill(email)

            # Mot de passe (requis sur certaines versions du formulaire LBC)
            import secrets as _s
            tmp_pwd = _s.token_urlsafe(12) + "!1A"  # satisfait les règles de complexité
            pwd_field = page.get_by_label(re.compile(r"mot de passe", re.I))
            if await pwd_field.count() > 0:
                await pwd_field.fill(tmp_pwd)

            await page.get_by_role("button", name=_BTN_RE).click()
            await page.wait_for_load_state("networkidle", timeout=20_000)
            log.info("Patchright : formulaire soumis")

            # ── 3. Code OTP SMS ──────────────────────────────────────────────
            sms_code = await boundaries.poll_sms(otp_order_id, max_wait=120)
            if sms_code is None:
                await boundaries.cancel_number(otp_order_id)
                raise AccountCreationError(f"Timeout OTP SMS order_id={otp_order_id}")
            log.info("Patchright : code OTP SMS=%s", sms_code)

            # Saisir dans le premier champ texte visible (page OTP)
            await page.get_by_role("textbox").first.fill(sms_code)
            await page.get_by_role("button", name=_BTN_RE).click()
            await page.wait_for_load_state("networkidle", timeout=20_000)

            # ── 4. Code vérification email (optionnel selon le flux LBC) ─────
            # Vérifie si LBC présente un champ de saisie supplémentaire.
            email_input_visible = await page.get_by_role("textbox").count() > 0
            if email_input_visible:
                email_code = await _poll_email_code_redis(email, timeout=_EMAIL_CODE_TIMEOUT)
                if email_code is None:
                    raise AccountCreationError(f"Timeout code vérification email pour {email}")
                log.info("Patchright : code email=%s", email_code)
                await page.get_by_role("textbox").first.fill(email_code)
                await page.get_by_role("button", name=_BTN_RE).click()
                await page.wait_for_load_state("networkidle", timeout=20_000)

            log.info("Patchright : inscription terminée — session persistée dans %s", session_path)

        finally:
            await ctx.close()


async def _create_with_browser_use(email: str, otp_order_id: str) -> None:
    """
    Fallback Mode B : browser-use Cloud REST API.

    Flux en 3 tâches séquentielles sur la même session (état navigateur partagé).
    La clé API vient de settings.browser_use_api_key (Bitwarden, règle R03).
    """
    import httpx as _httpx

    _base = "https://api.browser-use.com/api/v2"
    _headers = {
        "X-Browser-Use-API-Key": settings.browser_use_api_key,
        "Content-Type": "application/json",
    }

    async def _wait_for_task(client: _httpx.AsyncClient, task_id: str, timeout: int = 180) -> dict:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            r = await client.get(f"{_base}/tasks/{task_id}", headers=_headers)
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "")
            if status in ("finished", "completed", "done", "stopped"):
                return data
            if status in ("failed", "error"):
                raise AccountCreationError(f"browser-use tâche échouée : {data}")
            await asyncio.sleep(5)
        raise AccountCreationError(f"Timeout browser-use task_id={task_id}")

    async with _httpx.AsyncClient(timeout=30) as client:
        # Créer la session browser-use (proxy FR résidentiel inclus côté cloud)
        r = await client.post(f"{_base}/sessions", headers=_headers, json={})
        r.raise_for_status()
        session_id = r.json()["id"]
        log.info("browser-use Cloud : session créée=%s", session_id)

        try:
            # Tâche 1 — formulaire email
            r = await client.post(f"{_base}/tasks", headers=_headers, json={
                "session_id": session_id,
                "task": (
                    f"Ouvre {_LBC_SIGNUP_URL}. "
                    f"Remplis le champ email avec '{email}' et clique Continuer. "
                    "Arrête-toi dès que la page de vérification téléphone s'affiche."
                ),
            })
            r.raise_for_status()
            await _wait_for_task(client, r.json()["id"])
            log.info("browser-use Cloud : tâche 1 (formulaire email) terminée")

            # Tâche 2 — code OTP SMS
            sms_code = await boundaries.poll_sms(otp_order_id, max_wait=120)
            if sms_code is None:
                await boundaries.cancel_number(otp_order_id)
                raise AccountCreationError(f"Timeout OTP SMS order_id={otp_order_id}")

            r = await client.post(f"{_base}/tasks", headers=_headers, json={
                "session_id": session_id,
                "task": (
                    f"Saisis le code SMS '{sms_code}' dans le champ de vérification "
                    "et clique Valider. Arrête-toi à la page suivante."
                ),
            })
            r.raise_for_status()
            await _wait_for_task(client, r.json()["id"])
            log.info("browser-use Cloud : tâche 2 (OTP SMS) terminée")

            # Tâche 3 — code email (si présent dans le flux)
            email_code = await _poll_email_code_redis(email, timeout=_EMAIL_CODE_TIMEOUT)
            if email_code:
                r = await client.post(f"{_base}/tasks", headers=_headers, json={
                    "session_id": session_id,
                    "task": (
                        f"Saisis le code de vérification email '{email_code}' "
                        "et clique Valider pour finaliser la création du compte."
                    ),
                })
                r.raise_for_status()
                await _wait_for_task(client, r.json()["id"])
                log.info("browser-use Cloud : tâche 3 (code email) terminée")

        finally:
            await client.patch(
                f"{_base}/sessions/{session_id}",
                headers=_headers,
                json={"action": "stop"},
            )


async def create_lbc_account(mode: str = "A") -> CreationResult:
    """
    Crée un nouveau compte LBC.

    mode="A" : Patchright + iproxy 4G (principal, trust score maximal)
    mode="B" : browser-use Cloud (fallback si iproxy indisponible)

    Appelé par Celery task create_account_task.
    """
    account_uuid = str(uuid.uuid4())
    email = boundaries.generate_email()
    log.info("Création compte LBC — email=%s mode=%s id=%s", email, mode, account_uuid)

    # ── Proxy 4G (Mode A uniquement) ────────────────────────────────────────────
    proxy = None
    if mode == "A":
        rotated = await boundaries.rotate_4g_ip()
        if not rotated:
            raise ProxyUnavailableError("rotate_4g_ip() a échoué — iproxy.online indisponible.")
        await asyncio.sleep(35)   # délai post-rotation (règle : 30–60s)
        proxy = await boundaries.get_4g_proxy()
        await _verify_proxy_is_fr_carrier(proxy)
        log.info("Proxy 4G : %s | ASN: %s", proxy.url.split("@")[-1], proxy.asn_org)

    # ── Numéro OTP — SmsApp.io ──────────────────────────────────────────────────
    order = await boundaries.buy_number("france", "leboncoin")
    log.info("OTP acheté : phone=%s id=%s", order.phone, order.id)

    # ── Navigation et inscription ────────────────────────────────────────────────
    session_path = _session_path_for(account_uuid)
    if mode == "A" and proxy:
        await _create_with_patchright(email, proxy, session_path, order.id)
    else:
        await _create_with_browser_use(email, order.id)

    # ── Persistance DB — statut EN_CHAUFFE ───────────────────────────────────────
    async with get_db() as db:
        account = PlatformAccount(
            id=uuid.UUID(account_uuid),
            email=email,
            phone_otp=order.phone,
            status=AccountStatus.EN_CHAUFFE,
            datadome_trust_level=DatadomeTrustLevel.LOW,
            quota_actuel=10,
            session_path=session_path,
        )
        db.add(account)
        await db.flush()

    log.info("Compte créé : id=%s statut=EN_CHAUFFE warm-up 48–72h", account_uuid)
    return CreationResult(account_id=account_uuid, email=email, phone=order.phone, mode=mode)
