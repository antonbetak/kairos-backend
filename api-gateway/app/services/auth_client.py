from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import json
import httpx
import jwt
from jwt import PyJWKClient

from app.config import get_settings


logger = logging.getLogger("api_gateway.auth_client")
settings = get_settings()


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    if not settings.clerk_jwks_url:
        logger.debug("CLERK_JWKS_URL is missing, Clerk JWT verification will be disabled.")
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
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError:
        return None

    if response.status_code >= 400:
        return None

    return response.json()


async def _fetch_jwks() -> dict[str, Any] | None:
    if not settings.clerk_jwks_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.get(settings.clerk_jwks_url)
    except httpx.RequestError:
        return None

    if response.status_code >= 400:
        return None

    try:
        return response.json()
    except ValueError:
        return None


async def _decode_clerk_token(token: str) -> dict[str, Any] | None:
    client = _jwks_client()
    if client is None:
        return None

    signing_key = None
    payload = None

    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except Exception as exc:
        # Retry with manual JWKS fetch if PyJWKClient fails.
        try:
            jwks = await _fetch_jwks()
            if jwks and isinstance(jwks, dict):
                header = jwt.get_unverified_header(token)
                kid = header.get("kid")
                if kid and "keys" in jwks:
                    key_data = next(
                        (key for key in jwks["keys"] if key.get("kid") == kid),
                        None,
                    )
                    if key_data:
                        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(
                            json.dumps(key_data)
                        )
                        payload = jwt.decode(
                            token,
                            public_key,
                            algorithms=["RS256"],
                            options={"verify_aud": False},
                        )
        except Exception as retry_exc:
            logger.debug("Clerk token decode retry failed: %s", retry_exc)

        if payload is None:
            logger.debug("Clerk token could not be decoded: %s", exc)
            return None

    clerk_user_id = str(payload.get("sub") or "").strip()
    if not clerk_user_id:
        return None

    email = (
        str(
            payload.get("email")
            or payload.get("email_address")
            or payload.get("primary_email_address")
            or ""
        )
        .strip()
        .lower()
    )
    nombre = _full_name(payload)
    avatar_url = str(payload.get("image_url") or payload.get("picture") or "").strip()

    if not email or not nombre or not avatar_url:
        clerk_user = await _fetch_clerk_user(clerk_user_id)
        if clerk_user:
            email = email or (_primary_email_from_clerk_user(clerk_user) or "")
            nombre = nombre or _full_name(clerk_user)
            avatar_url = (
                avatar_url
                or str(
                    clerk_user.get("image_url")
                    or clerk_user.get("profile_image_url")
                    or ""
                ).strip()
            )

    if not email:
        return None

    return {
        "clerk_id": clerk_user_id,
        "email": email,
        "nombre": nombre,
        "avatar_url": avatar_url or None,
    }


async def _sync_clerk_user(profile: dict[str, Any]) -> dict[str, Any] | None:
    url = f"{settings.google_auth_url.rstrip('/')}/auth/google/clerk/session"
    headers = {}
    if settings.internal_service_token:
        headers["X-Internal-Token"] = settings.internal_service_token

    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds
        ) as client:
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
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds
        ) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        return None

    if response.status_code == 200:
        return response.json()

    return None


def is_clerk_token(token: str) -> bool:
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return False

    alg = str(header.get("alg") or "").upper()
    kid = header.get("kid")
    return alg.startswith("RS") and bool(kid)


async def get_clerk_id_from_token(token: str) -> str | None:
    if not is_clerk_token(token):
        return None

    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            leeway=60,
        )
    except Exception as exc:
        logger.debug("Clerk token decode failed in get_clerk_id_from_token: %s", exc)
        return None

    clerk_user_id = str(payload.get("sub") or payload.get("user_id") or "").strip()
    return clerk_user_id or None


async def verify_token(token: str) -> dict[str, Any] | None:
    is_clerk_token = False
    try:
        header = jwt.get_unverified_header(token)
        alg = str(header.get("alg") or "").upper()
        kid = header.get("kid")
        if alg.startswith("RS") and kid:
            is_clerk_token = True
    except Exception:
        is_clerk_token = False

    clerk_profile = await _decode_clerk_token(token)
    if clerk_profile:
        kairos_user = await _sync_clerk_user(clerk_profile)
        if kairos_user:
            return kairos_user

    if is_clerk_token:
        logger.debug("Token appears to be Clerk-issued and did not decode correctly; skipping legacy Kairos verify.")
        return None

    return await _verify_legacy_kairos_token(token)
