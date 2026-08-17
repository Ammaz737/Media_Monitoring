"""Password hashing, signed tokens, and role permissions."""

import hashlib
import hmac
import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import WEB_CONFIG

ROLES = ("admin", "operator", "viewer")
ROLE_PERMS = {
    "viewer": frozenset({"read"}),
    "operator": frozenset({"read", "operate", "configure"}),
    "admin": frozenset({"read", "operate", "configure", "users"}),
}
PBKDF2_ITERS = 200_000
TOKEN_MAX_AGE = 7 * 24 * 3600


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"), PBKDF2_ITERS
    )
    return f"pbkdf2${PBKDF2_ITERS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, hexdk = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hexdk)
    except (ValueError, TypeError):
        return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(WEB_CONFIG["secret_key"], salt="nm-auth")


def issue_token(user_id: int) -> str:
    return _serializer().dumps({"uid": int(user_id)})


def parse_token(token: str) -> Optional[int]:
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE)
        return int(data["uid"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None


def perms_for(role: str) -> frozenset:
    return ROLE_PERMS.get(role or "", frozenset())


def public_user(row: dict) -> dict:
    role = row["role"]
    return {
        "id": row["id"],
        "username": row["username"],
        "role": role,
        "is_active": bool(row.get("is_active", True)),
        "permissions": sorted(perms_for(role)),
    }
