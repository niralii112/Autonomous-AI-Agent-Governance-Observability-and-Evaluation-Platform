"""Password hashing (bcrypt) and access tokens (JWT, HS256). Spec sections 9.7 and 18.

Signatures here are internal to Student 1 (the spec lists the function names only).

Passwords: the contract allows 128-character passwords, but bcrypt only reads the first
72 bytes (and bcrypt 5 raises an error on longer input). So the password is first turned
into a fixed 44-character string with SHA-256 + base64, and that is what bcrypt hashes.
This is the standard way to support long passwords and means two long passwords that
differ only after byte 72 still get different hashes.
"""

import base64
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.enums import ErrorCode, UserRole
from app.core.exceptions import AppError

BCRYPT_ROUNDS = 12  # tests lower this for speed
JWT_ALGORITHM = "HS256"  # the only algorithm we ever accept when decoding
REQUIRED_CLAIMS = ("sub", "username", "role", "iss", "iat", "exp")


def _prepare(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """True only if the password matches. Never raises for a malformed hash."""
    if not isinstance(password_hash, str):
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


_dummy_hash: str | None = None


def burn_password_check(password: str) -> None:
    """Spend the same time as a real check. Used when the username does not exist, so login
    timing does not reveal which usernames are real (spec section 18, no user enumeration)."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


def create_access_token(user_id: uuid.UUID, username: str, role: UserRole) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": UserRole(role).value,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_token_expire_minutes)).timestamp()),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=JWT_ALGORITHM)


def access_token_lifetime_seconds() -> int:
    """The 'expires_in' value returned by login."""
    return get_settings().jwt_access_token_expire_minutes * 60


def decode_access_token(token: str) -> dict[str, Any]:
    """Return the claims of a valid token.

    Raises AppError AUTH_TOKEN_EXPIRED (exp in the past) or AUTH_TOKEN_INVALID (anything else).
    Only HS256 is accepted, so tokens using "none" or another algorithm are rejected.
    """
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            issuer=settings.jwt_issuer,
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.ExpiredSignatureError:
        raise AppError(ErrorCode.AUTH_TOKEN_EXPIRED, "The access token has expired.") from None
    except jwt.PyJWTError:
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "The access token is not valid.") from None

    try:
        uuid.UUID(str(claims["sub"]))
        UserRole(claims["role"])
    except (ValueError, KeyError):
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "The access token is not valid.") from None
    return claims
