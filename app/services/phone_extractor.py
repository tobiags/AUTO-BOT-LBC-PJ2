"""
Extraction de numéro de téléphone depuis le texte d'une annonce.
Stratégie : regex d'abord, Claude Haiku en fallback si ambiguïté.
"""
import re

# Formats FR courants : 06XXXXXXXX, +336XXXXXXXX, 06 XX XX XX XX, etc.
_PHONE_PATTERNS = [
    r"(?:\+33|0033|0)\s*[67](?:\s*\d{2}){4}",  # mobile FR
    r"(?:\+33|0033|0)\s*[1-9](?:\s*\d{2}){4}",  # fixe FR
]
_PHONE_RE = re.compile("|".join(_PHONE_PATTERNS))


def _normalize(raw: str) -> str:
    """Normalise vers +33XXXXXXXXX."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("33") and len(digits) == 11:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:
        return "+33" + digits[1:]
    return "+" + digits


def extract_phone(text: str) -> str | None:
    """Regex synchrone — ne consomme pas de tokens API."""
    match = _PHONE_RE.search(text)
    if match:
        return _normalize(match.group())
    return None


async def extract_phone_with_fallback(text: str) -> str | None:
    """
    Essaie le regex d'abord.
    Si None → appel Claude Haiku (boundaries.extract_phone_llm).
    Coût Haiku : ~0.001 € / appel — uniquement si regex échoue.
    """
    result = extract_phone(text)
    if result:
        return result

    # Fallback IA uniquement si le texte semble contenir un numéro
    # (évite des appels Haiku sur des textes sans numéro du tout)
    if not any(c.isdigit() for c in text):
        return None

    from app import boundaries
    return await boundaries.extract_phone_llm(text)
