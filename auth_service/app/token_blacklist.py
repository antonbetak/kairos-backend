from __future__ import annotations

from datetime import datetime
from datetime import timezone
import hashlib

from app.redis_client import redis_client


BLACKLIST_QUEUE_KEY = "auth:blacklist:queue"
BLACKLIST_PREFIX = "auth:blacklist:"


def _token_key(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{BLACKLIST_PREFIX}{digest}"


def is_token_blacklisted(token: str) -> bool:
    key = _token_key(token)
    return redis_client.exists(key) == 1


def blacklist_token(token: str, expires_at: datetime | None) -> None:
    key = _token_key(token)
    ttl_seconds = 0
    if expires_at:
        ttl_seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())

    if ttl_seconds <= 0:
        ttl_seconds = 60

    redis_client.setex(key, ttl_seconds, "1")
    redis_client.lpush(BLACKLIST_QUEUE_KEY, key)
