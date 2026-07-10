"""
SEUL fichier autorisé à appeler des APIs externes.

Toute la logique métier passe par ces fonctions.
En test, on mocke uniquement ce module — jamais les services internes.

Règle R07 : ne jamais passer l'IP du VPS à get_4g_proxy().
Règle R03 : les clés API viennent de Settings, jamais hardcodées.
"""
import asyncio
import logging
import secrets

import httpx

from app.config import get_settings
from app.models import ActivationOrder, ProxyInfo, SmsResult, SmsStatus

settings = get_settings()
log = logging.getLogger(__name__)

# ── SMSTOOLS ─────────────────────────────────────────────────────────────────

_SMSTOOLS_BASE = "https://api.smstools.online/v1"


class InsufficientCreditError(RuntimeError):
    """SMSTools a refusé l'envoi faute de crédit disponible."""


async def send_sms(sim_id: str, to: str, body: str) -> SmsResult:
    """Envoie un SMS depuis la SIM spécifiée via SMSTools REST API."""
    async with httpx.AsyncClient(timeout=15) as client:
        for attempt in range(1, 4):
            try:
                resp = await client.post(
                    f"{_SMSTOOLS_BASE}/messages",
                    headers={"Authorization": f"Bearer {settings.smstools_api_key}"},
                    json={"sim_id": sim_id, "to": to, "body": body},
                )
                if resp.status_code == 402:
                    raise InsufficientCreditError(
                        f"SMSTools crédit insuffisant pour la SIM {sim_id}"
                    )
                if resp.status_code == 429 and attempt < 3:
                    backoff = 2 ** attempt
                    log.warning(
                        "SMSTools rate limit sur %s - retry %d/3 dans %ds",
                        sim_id,
                        attempt,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return SmsResult(
                    id=data["id"],
                    status=SmsStatus.SENT if data.get("status") == "sent" else SmsStatus.FAILED,
                    cost=data.get("cost", 0.0),
                    sim_id=sim_id,
                    to=to,
                )
            except InsufficientCreditError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= 3:
                    raise
                backoff = 2 ** attempt
                log.warning(
                    "SMSTools erreur réseau sur %s - retry %d/3 dans %ds: %s",
                    sim_id,
                    attempt,
                    backoff,
                    exc,
                )
                await asyncio.sleep(backoff)
        raise RuntimeError(f"SMSTools: échec envoi après 3 tentatives (SIM {sim_id})")


async def get_sim_list() -> list[dict]:
    """Retourne la liste des SIMs actives et leurs quotas."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_SMSTOOLS_BASE}/sims",
            headers={"Authorization": f"Bearer {settings.smstools_api_key}"},
        )
        resp.raise_for_status()
        return resp.json()["sims"]


# ── IPROXY.ONLINE ────────────────────────────────────────────────────────────

_IPROXY_BASE = "https://iproxy.online/api/console/v1"


async def get_4g_proxy() -> ProxyInfo:
    """
    Retourne le proxy 4G mobile français actif.
    RÈGLE R07 : cette fonction est le seul endroit autorisé pour obtenir
    l'IP 4G. Ne jamais passer l'IP VPS comme proxy LBC.
    """
    if not settings.iproxy_connection_id:
        raise ValueError("IPROXY_CONNECTION_ID is required")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_IPROXY_BASE}/connection/{settings.iproxy_connection_id}/proxy-access",
            headers={"Authorization": f"Bearer {settings.iproxy_api_key}"},
        )
        resp.raise_for_status()
        accesses = resp.json()["proxy_accesses"]
        proxy = next(
            (a for a in accesses if a["id"] == settings.iproxy_proxy_id),
            accesses[0],
        )
        auth = proxy["auth"]
        scheme = proxy["listen_service"]
        url = f"{scheme}://{auth['login']}:{auth['password']}@{proxy['hostname']}:{proxy['port']}"
        return ProxyInfo(url=url)


async def rotate_4g_ip() -> bool:
    """Demande une rotation d'IP — attendre 30–60s avant de réutiliser."""
    if not settings.iproxy_connection_id:
        raise ValueError("IPROXY_CONNECTION_ID is required")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_IPROXY_BASE}/connection/{settings.iproxy_connection_id}/command-push",
            headers={"Authorization": f"Bearer {settings.iproxy_api_key}"},
            json={"action": "changeip"},
        )
        return resp.status_code == 200


# ── SMSAPP.IO (OTP) ───────────────────────────────────────────────────────────

_SMSAPP_BASE = "https://backend.smsapp.io/v1"


async def buy_number(country: str, service: str) -> ActivationOrder:
    """Achète un numéro OTP jetable. Pay-per-delivery — remboursé si SMS non reçu."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_SMSAPP_BASE}/buy",
            headers={"Authorization": f"Bearer {settings.smsapp_api_token}"},
            json={"country": country, "service": service},
        )
        resp.raise_for_status()
        data = resp.json()
        return ActivationOrder(
            id=str(data["id"]),
            phone=data["phone"],
            country=country,
            service=service,
            cost=data.get("cost", 0.0),
            expires=data.get("expires", 0),
        )


async def poll_sms(order_id: str, max_wait: int = 120) -> str | None:
    """
    Poll jusqu'à réception du SMS OTP.
    Retourne le code extrait ou None si timeout.
    L'appelant doit appeler cancel_number() en cas de None.
    """
    import asyncio
    import re

    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_wait
    while loop.time() < deadline:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{_SMSAPP_BASE}/sms/{order_id}",
                headers={"Authorization": f"Bearer {settings.smsapp_api_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "RECEIVED" and data.get("sms"):
                text = data["sms"][0].get("text", "")
                codes = re.findall(r"\b\d{4,8}\b", text)
                if codes:
                    return codes[0]
        await asyncio.sleep(3)
    return None


async def cancel_number(order_id: str) -> bool:
    """Annule et rembourse un numéro OTP non utilisé."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_SMSAPP_BASE}/cancel/{order_id}",
            headers={"Authorization": f"Bearer {settings.smsapp_api_token}"},
        )
        return resp.status_code == 200


# ── MAILGUN ───────────────────────────────────────────────────────────────────

def generate_email(domain: str | None = None) -> str:
    """
    Génère une adresse email d'apparence réaliste pour un nouveau compte LBC.
    Format : prenom.nom[@][suffixe_optionnel]@{operational_domain}
    Jamais réutilisée — combinaison aléatoire + suffixe unique.
    """
    domain = domain or settings.operational_domain
    return f"contact.{secrets.token_hex(4)}@{domain}"
