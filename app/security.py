import hashlib
import hmac
import secrets
import time
from typing import Annotated

from fastapi import Header, HTTPException, Query

from app.config import get_settings


def require_control_role(role: str, minimum: str) -> None:
    aliases = {
        "operateur": "operator",
        "manager": "operator",
        "administrateur": "admin",
    }
    normalized = aliases.get(role.lower(), role.lower())
    rank = {"viewer": 0, "operator": 1, "admin": 2}
    if minimum not in rank or rank.get(normalized, -1) < rank[minimum]:
        raise HTTPException(403, detail={"code": "INSUFFICIENT_ROLE"})


def require_control_token(x_control_tower_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().control_tower_token
    if not expected:
        raise HTTPException(503, detail={"code": "CONTROL_TOWER_NOT_CONFIGURED"})
    if x_control_tower_token is None or not secrets.compare_digest(x_control_tower_token, expected):
        raise HTTPException(401, detail={"code": "UNAUTHORIZED"})


def require_webhook_secret(
    x_webhook_secret: Annotated[str | None, Header()] = None,
    secret: Annotated[str | None, Query()] = None,
) -> None:
    expected = get_settings().smstools_webhook_secret
    supplied = x_webhook_secret or secret
    if not expected:
        raise HTTPException(503, detail={"code": "WEBHOOK_SECRET_NOT_CONFIGURED"})
    if supplied is None or not secrets.compare_digest(supplied, expected):
        raise HTTPException(401, detail={"code": "INVALID_WEBHOOK_SIGNATURE"})


def verify_mailgun_signature(timestamp: str, token: str, signature: str) -> None:
    try:
        age = abs(time.time() - int(timestamp))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, detail={"code": "INVALID_WEBHOOK_SIGNATURE"}) from exc
    if age > 900:
        raise HTTPException(401, detail={"code": "EXPIRED_WEBHOOK_SIGNATURE"})
    key = get_settings().mailgun_webhook_signing_key
    if not key:
        raise HTTPException(503, detail={"code": "MAILGUN_SIGNING_KEY_NOT_CONFIGURED"})
    expected = hmac.new(key.encode(), f"{timestamp}{token}".encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        raise HTTPException(401, detail={"code": "INVALID_WEBHOOK_SIGNATURE"})


def websocket_token_is_valid(token: str | None) -> bool:
    key = get_settings().control_tower_token
    if not key or not token:
        return False
    try:
        expires, signature = token.split(".", 1)
        if int(expires) < int(time.time()):
            return False
    except (TypeError, ValueError):
        return False
    expected = hmac.new(key.encode(), expires.encode(), hashlib.sha256).hexdigest()
    return secrets.compare_digest(signature, expected)
