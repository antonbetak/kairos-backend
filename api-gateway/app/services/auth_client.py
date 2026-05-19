from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from app.config import get_settings


settings = get_settings()


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    if not settings.clerk_jwks_url:
        return None
    return PyJWKClient(settings.clerk_jwks_url)


def _full_name(profile: dict[str, Any]) -> str | None:
    first_name = str(profile.get("first_name") or "").strip()
    last_name = str(profile.get("last_name") or "").strip()
    name = " ".join(part for part in (first_name, last_name) if part).strip()
    return name or str(profile.get("name") or "").strip() or None


def _primary_email_from_clerk_user(user: dict[str, Any]) -> str | None:
    primary_id = user.get("primary_email_address_id")
    email_addresses = user.get("email_addresses") or []

    for item in email_addresses:
        if item.get("id") == primary_id and item.get("email_address"):
            return str(item["email_address"]).strip().lower()

    for item in email_addresses:
        if item.get("email_address"):
            return str(item["email_address"]).strip().lower()

    return None


async def _fetch_clerk_user(clerk_user_id: str) -> dict[str, Any] | None:
    if not settings.clerk_secret_key:
        return None

    url = f"https://api.clerk.com/v1/users/{clerk_user_id}"
    headers = {"Authorization": f"Bearer {settings.clerk_secret_key}"}
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError:
        return None

    if response.status_code >= 400:
        return None

    return response.json()


async def _decode_clerk_token(token: str) -> dict[str, Any] | None:
    client = _jwks_client()
    if client is None:
        return None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None

    clerk_user_id = str(payload.get("sub") or "").strip()
    if not clerk_user_id:
        return None

    email = str(
        payload.get("email")
        or payload.get("email_address")
        or payload.get("primary_email_address")
        or ""
    ).strip().lower()
    nombre = _full_name(payload)
    avatar_url = str(payload.get("image_url") or payload.get("picture") or "").strip()

    if not email or not nombre or not avatar_url:
        clerk_user = await _fetch_clerk_user(clerk_user_id)
        if clerk_user:
            email = email or (_primary_email_from_clerk_user(clerk_user) or "")
            nombre = nombre or _full_name(clerk_user)
            avatar_url = avatar_url or str(
                clerk_user.get("image_url") or clerk_user.get("profile_image_url") or ""
            ).strip()

    if not email:
        return None

    return {
        "clerk_id": clerk_user_id,
        "email": email,
        "nombre": nombre,
        "avatar_url": avatar_url or None,
    }


async def _sync_clerk_user(profile: dict[str, Any]) -> dict[str, Any] | None:
    url = f"{settings.auth_service_url.rstrip('/')}/auth/clerk/sync"
    headers = {}
    if settings.internal_service_token:
        headers["X-Internal-Token"] = settings.internal_service_token

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(url, json=profile, headers=headers)
    except httpx.RequestError:
        return None

    if response.status_code != 200:
        return None

    user = response.json()
    return {
        "valid": True,
        "id_usuario": user.get("id_usuario"),
        "email": user.get("email"),
        "handle": user.get("handle"),
        "nombre": user.get("nombre"),
        "avatar_url": user.get("avatar_url"),
        "auth_provider": "clerk",
        "clerk_id": user.get("clerk_id") or profile.get("clerk_id"),
    }


async def _verify_legacy_kairos_token(token: str) -> dict[str, Any] | None:
    url = f"{settings.auth_service_url.rstrip('/')}/auth/verify"
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        return None

    if response.status_code == 200:
        return response.json()

    return None


async def verify_token(token: str) -> dict[str, Any] | None:
    clerk_profile = await _decode_clerk_token(token)
    if clerk_profile:
        kairos_user = await _sync_clerk_user(clerk_profile)
        if kairos_user:
            return kairos_user

    return await _verify_legacy_kairos_token(token)
