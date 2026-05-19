from __future__ import annotations

import logging
from functools import wraps

import httpx
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class AuthContext(BaseModel):
    user_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None


async def _tokeninfo(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            settings.google_tokeninfo_uri, params={"access_token": access_token}
        )

    if response.status_code >= 400:
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


def _verify_gateway_token(internal_token: str | None) -> None:
    if not settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token interno de servicio no configurado.",
        )

    if not internal_token or internal_token != settings.internal_service_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere X-Internal-Token válido.",
        )


def _select_google_token(
    google_token: str | None,
) -> str:
    if google_token and str(google_token).strip():
        return str(google_token).strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere X-Google-Access-Token.",
    )


async def require_auth(
    x_internal_token: str | None = Header(
        None,
        alias="X-Internal-Token",
        description="Token interno enviado por el gateway",
    ),
    google_token: str | None = Header(
        None,
        alias="X-Google-Access-Token",
        description="Google access token interno",
    ),
    google_refresh: str | None = Header(
        None,
        alias="X-Google-Refresh-Token",
    ),
) -> AuthContext:
    logger.info(
        "Calendar require_auth headers x-internal-token=%s x-google-access-token=%s x-google-refresh-token=%s",
        bool(x_internal_token),
        google_token,
        google_refresh,
    )

    _verify_gateway_token(x_internal_token)

    if not google_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere X-Google-Access-Token.",
        )

    google_access_token = _select_google_token(google_token)

    token_info = None
    try:
        token_info = await _tokeninfo(google_access_token)
    except HTTPException as exc:
        if google_refresh and exc.status_code == status.HTTP_401_UNAUTHORIZED:
            google_access_token = await _refresh_access_token(google_refresh)
            token_info = await _tokeninfo(google_access_token)
        else:
            raise

    if token_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido o expirado.",
        )

    if str(token_info.get("aud") or "").strip() not in (
        "",
        settings.google_client_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no pertenece a este cliente OAuth.",
        )

    google_user_id = str(
        token_info.get("sub") or token_info.get("user_id") or ""
    ).strip()
    if not google_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No fue posible identificar al usuario de Google.",
        )

    return AuthContext(
        user_id=google_user_id,
        access_token=google_access_token,
        refresh_token=google_refresh,
    )


def require_jwt(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    if not auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT requerido para acceder a endpoints de dispositivo.",
        )

    return auth


def require_google_login(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        auth = kwargs.get("auth")
        if auth is None:
            for arg in args:
                if isinstance(arg, AuthContext):
                    auth = arg
                    break

        if not auth or not auth.access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Debe iniciar sesion con Google (X-Google-Access-Token).",
            )

        return await func(*args, **kwargs)

    return wrapper
