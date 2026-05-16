from __future__ import annotations

from datetime import datetime
from datetime import timezone
import hashlib

from jose import JWTError
from jose import jwt

from app.redis_client import redis_client


BLACKLIST_QUEUE_KEY = "auth:blacklist:queue"
BLACKLIST_PREFIX = "auth:blacklist:"
BLACKLIST_SESSION_PREFIX = "auth:blacklist:session:"


def _token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{BLACKLIST_PREFIX}{digest}"


def _session_key(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return f"{BLACKLIST_SESSION_PREFIX}{digest}"


def _token_session_id(token: str) -> str:
    try:
        claims = jwt.get_unverified_claims(token)
    except JWTError:
        return ""

    return str(claims.get("sid") or "").strip()


def is_token_blacklisted(token: str) -> bool:
    key = _token_key(token)
    if redis_client.exists(key) == 1:
        return True

    session_id = _token_session_id(token)
    if not session_id:
        return False

    return redis_client.exists(_session_key(session_id)) == 1


def is_session_blacklisted(session_id: str) -> bool:
    return redis_client.exists(_session_key(session_id)) == 1


def blacklist_token(token: str, expires_at: datetime | None) -> None:
    key = _token_key(token)
    ttl_seconds = 0
    if expires_at:
        ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())

    if ttl_seconds <= 0:
        ttl_seconds = 60

    redis_client.setex(key, ttl_seconds, "1")
    redis_client.lpush(BLACKLIST_QUEUE_KEY, key)


def blacklist_session(session_id: str, expires_at: datetime | None) -> None:
    key = _session_key(session_id)
    ttl_seconds = 0
    if expires_at:
        ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())

    if ttl_seconds <= 0:
        ttl_seconds = 60

    redis_client.setex(key, ttl_seconds, "1")
    redis_client.lpush(BLACKLIST_QUEUE_KEY, key)
