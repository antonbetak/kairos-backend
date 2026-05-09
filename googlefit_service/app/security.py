from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class FitAuthContext(BaseModel):
    user_id: str
    access_token: str
    scopes: list[str]
    expires_in: int | None = None
    refreshed: bool = False


async def _tokeninfo(access_token: str) -> dict[str, Any]:
    params = {"access_token": access_token}
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.get(settings.google_tokeninfo_uri, params=params)

    if response.status_code >= 400:
        logger.warning("Google tokeninfo failed: %s", response.text)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido o expirado.",
        )

    return response.json()


async def _refresh_access_token(refresh_token: str) -> str:
    payload = {
        "refresh_token": refresh_token,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(settings.google_token_uri, data=payload)

    if response.status_code >= 400:
        logger.warning("Google token refresh failed: %s", response.text)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No fue posible refrescar el access_token de Google.",
        )

    token_response = response.json()
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google no devolvió un access_token válido.",
        )

    return access_token


def _validate_scopes(token_scopes: str) -> list[str]:
    scopes = [scope.strip() for scope in token_scopes.split() if scope.strip()]
    required = settings.fit_scopes_list()
    missing = [scope for scope in required if scope not in scopes]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El token de Google no tiene los permisos requeridos.",
        )

    return scopes


async def require_google_token(
    google_token: str = Header(..., alias="X-Google-Token", description="Google access_token"),
    google_refresh: str | None = Header(None, alias="X-Google-Refresh"),
) -> FitAuthContext:
    access_token = google_token.strip()
    refreshed = False

    try:
        token_info = await _tokeninfo(access_token)
    except HTTPException:
        if not google_refresh:
            raise
        access_token = await _refresh_access_token(google_refresh)
        token_info = await _tokeninfo(access_token)
        refreshed = True

    aud = str(token_info.get("aud") or "").strip()
    if aud and aud != settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no pertenece a este cliente OAuth.",
        )

    user_id = str(token_info.get("sub") or token_info.get("user_id") or "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No fue posible identificar al usuario.",
        )

    expires_in = token_info.get("expires_in")
    try:
        expires_in_value = int(expires_in) if expires_in is not None else None
    except (TypeError, ValueError):
        expires_in_value = None

    scopes = _validate_scopes(str(token_info.get("scope") or ""))

    return FitAuthContext(
        user_id=user_id,
        access_token=access_token,
        scopes=scopes,
        expires_in=expires_in_value,
        refreshed=refreshed,
    )
