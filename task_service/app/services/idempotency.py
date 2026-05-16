from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from uuid import UUID

from redis.exceptions import RedisError

from app.redis_client import redis_client


PROCESSING_TTL_SECONDS = 60
COMPLETED_TTL_SECONDS = 60 * 60 * 24


@dataclass(frozen=True)
class IdempotencyReservation:
    acquired: bool
    state: str | None


def build_key(service_name: str, operation_id: UUID | str) -> str:
    return f"idempotency:{service_name}:{operation_id}"


def reserve(service_name: str, operation_id: UUID | str) -> IdempotencyReservation:
    key = build_key(service_name, operation_id)
    try:
        acquired = redis_client.set(key, "PROCESSING", nx=True, ex=PROCESSING_TTL_SECONDS)
        if acquired:
            return IdempotencyReservation(acquired=True, state="PROCESSING")

        state = redis_client.get(key)
        return IdempotencyReservation(acquired=False, state=state)
    except RedisError:
        return IdempotencyReservation(acquired=True, state=None)


def complete(service_name: str, operation_id: UUID | str, payload: dict[str, str] | None = None) -> None:
    key = build_key(service_name, operation_id)
    value = {
        "state": "COMPLETED",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if payload:
        value.update(payload)

    try:
        redis_client.setex(key, COMPLETED_TTL_SECONDS, json.dumps(value))
    except RedisError:
        return


def fail(service_name: str, operation_id: UUID | str) -> None:
    key = build_key(service_name, operation_id)
    try:
        redis_client.delete(key)
    except RedisError:
        return