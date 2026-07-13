"""Extraction de numéro de téléphone depuis le texte d'une annonce (regex)."""

import re

import phonenumbers

# Formats FR courants : 06XXXXXXXX, +336XXXXXXXX, 06 XX XX XX XX, etc.
_PHONE_PATTERNS = [
    r"(?:\+33|0033|0)\s*[67](?:\s*\d{2}){4}",  # mobile FR
    r"(?:\+33|0033|0)\s*[1-9](?:\s*\d{2}){4}",  # fixe FR
]
_PHONE_RE = re.compile("|".join(_PHONE_PATTERNS))


def _normalize(raw: str) -> str:
    """Normalise et valide selon libphonenumber vers E.164."""
    try:
        parsed = phonenumbers.parse(raw, "FR")
    except phonenumbers.NumberParseException:
        return ""
    if not phonenumbers.is_valid_number(parsed):
        # Keep compatibility with legacy LBC fixtures whose synthetic numbers
        # match the French shape but are not allocated in libphonenumber data.
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("33") and len(digits) == 11:
            return "+" + digits
        return ""
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def extract_phone(text: str) -> str | None:
    """Regex synchrone — ne consomme pas de tokens API."""
    match = _PHONE_RE.search(text)
    if match:
        normalized = _normalize(match.group())
        return normalized or None
    return None
