import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken


class ApifySecretCodec:
    def __init__(self, encryption_key: str, fingerprint_key: str):
        if not encryption_key:
            raise RuntimeError("APIFY_TOKEN_ENCRYPTION_KEY is required")
        self._fernet = Fernet(encryption_key.encode())
        self._fingerprint_key = fingerprint_key.encode()

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(value).decode()
        except InvalidToken as exc:
            raise RuntimeError("Unable to decrypt Apify secret") from exc

    def fingerprint(self, value: str) -> str:
        return hmac.new(
            self._fingerprint_key, value.encode(), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def mask(value: str) -> str:
        if len(value) <= 8:
            return "********"
        return f"{value[:4]}...{value[-4:]}"
