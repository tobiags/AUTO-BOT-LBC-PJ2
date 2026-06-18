"""
SEUL fichier autorisé à appeler des APIs externes.

Toute la logique métier passe par ces fonctions.
En test, on mocke uniquement ce module — jamais les services internes.

Règle R07 : ne jamais passer l'IP du VPS à get_4g_proxy().
Règle R03 : les clés API viennent de Settings, jamais hardcodées.
"""
import httpx

from app.config import get_settings
from app.models import ActivationOrder, ProxyInfo, SmsResult, SmsStatus

settings = get_settings()

# ── SMSTOOLS ─────────────────────────────────────────────────────────────────

_SMSTOOLS_BASE = "https://api.smstools.org/v1"


async def send_sms(sim_id: str, to: str, body: str) -> SmsResult:
    """Envoie un SMS depuis la SIM spécifiée via SMSTools REST API."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_SMSTOOLS_BASE}/messages",
            headers={"Authorization": f"Bearer {settings.smstools_api_key}"},
            json={"sim_id": sim_id, "to": to, "body": body},
        )
        resp.raise_for_status()
        data = resp.json()
        return SmsResult(
            id=data["id"],
            status=SmsStatus.SENT if data.get("status") == "sent" else SmsStatus.FAILED,
            cost=data.get("cost", 0.0),
            sim_id=sim_id,
            to=to,
        )


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

_IPROXY_BASE = "https://iproxy.online/api/v1"


async def get_4g_proxy() -> ProxyInfo:
    """
    Retourne le proxy 4G mobile français actif.
    RÈGLE R07 : cette fonction est le seul endroit autorisé pour obtenir
    l'IP 4G. Ne jamais passer l'IP VPS comme proxy LBC.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{_IPROXY_BASE}/proxy/{settings.iproxy_proxy_id}",
            headers={"Authorization": f"Bearer {settings.iproxy_api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return ProxyInfo(
            url=data["proxy_url"],
            asn_org=data.get("asn_org", ""),
            country=data.get("country", "FR"),
        )


async def rotate_4g_ip() -> bool:
    """Demande une rotation d'IP — attendre 30–60s avant de réutiliser."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_IPROXY_BASE}/proxy/{settings.iproxy_proxy_id}/rotate",
            headers={"Authorization": f"Bearer {settings.iproxy_api_key}"},
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

    deadline = asyncio.get_event_loop().time() + max_wait
    while asyncio.get_event_loop().time() < deadline:
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

import secrets


def generate_email(domain: str | None = None) -> str:
    """
    Génère une adresse email unique pour un nouveau compte LBC.
    Format : contact.{8 hex chars}@{operational_domain}
    Jamais réutilisée — token unique par compte.
    """
    domain = domain or settings.operational_domain
    token = secrets.token_hex(4)
    return f"contact.{token}@{domain}"


# ── ANTHROPIC (Claude Haiku — fallback extraction numéro) ────────────────────

async def extract_phone_llm(text: str) -> str | None:
    """
    Fallback quand le regex échoue à extraire un numéro de téléphone ambigu.
    Utilise Claude Haiku (~0.001 € / appel). Appelé uniquement si regex = None.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": (
                f"Extrait le numéro de téléphone français de ce texte. "
                f"Réponds uniquement avec le numéro au format +33XXXXXXXXX ou null.\n\n{text}"
            ),
        }],
    )
    result = msg.content[0].text.strip()
    return None if result.lower() == "null" else result
