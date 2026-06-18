"""Extraction de numéro de téléphone depuis le texte d'une annonce (regex)."""
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


