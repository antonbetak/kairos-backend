from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import UUID

from jose import JWTError
from jose import jwt

from app.config import settings


def create_access_token(user_id: UUID, email: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expires_at,
        "type": "access",
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: UUID, email: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_refresh_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expires_at,
        "type": "refresh",
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def decode_refresh_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") not in (None, "refresh"):
        raise JWTError("Invalid refresh token type")
    return payload


def get_token_expiration(token: str) -> datetime | None:
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        return None

    exp = claims.get("exp")
    if exp is None:
        return None

    if isinstance(exp, (int, float)):
        return datetime.fromtimestamp(exp, tz=timezone.utc)

    if isinstance(exp, datetime):
        return exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)

    try:
        return datetime.fromtimestamp(float(exp), tz=timezone.utc)
    except (TypeError, ValueError):
        return None
