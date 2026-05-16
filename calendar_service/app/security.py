from __future__ import annotations

import logging
from functools import wraps

import httpx
import jwt
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
        response = await client.get(settings.google_tokeninfo_uri, params={"access_token": access_token})

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Google inválido o expirado.",
        )

    return response.json()


async def _token_status(token: str) -> bool:
    url = f"{settings.auth_service_url.rstrip('/')}/auth/token-status"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json={"token": token})

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible validar el estado del token.",
        )

    return bool(response.json().get("blacklisted"))


async def _blacklist_token(token: str) -> None:
    url = f"{settings.auth_service_url.rstrip('/')}/auth/token-blacklist"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json={"token": token})

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible invalidar el token anterior.",
        )


async def _verify_internal_token(authorization: str) -> dict:
    url = f"{settings.auth_service_url.rstrip('/')}/auth/verify"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers={"Authorization": authorization})

    if response.status_code == 200:
        return response.json()

    if response.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT inválido o expirado.",
        )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No fue posible validar el JWT interno.",
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header Authorization.",
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization debe ser 'Bearer <token>'.",
        )

    return parts[1]


def _select_google_token(
    authorization: str | None,
    google_token: str | None,
) -> str:
    if google_token and str(google_token).strip():
        return str(google_token).strip()

    if authorization:
        return _extract_bearer_token(authorization)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere Authorization o X-Google-Token.",
    )


async def require_auth(
    authorization: str | None = Header(None, description="Bearer JWT interno"),
    google_token: str | None = Header(None, alias="X-Google-Token", description="Google access_token"),
    google_refresh: str | None = Header(None, alias="X-Google-Refresh"),
) -> AuthContext:
    if not authorization and not google_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere Authorization o X-Google-Token.",
        )

    if google_token and str(google_token).strip():
        access_token = _select_google_token(authorization, google_token)

        if await _token_status(access_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de Google invalidado.",
            )

        token_info = await _tokeninfo(access_token)
        if str(token_info.get("aud") or "").strip() not in ("", settings.google_client_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token no pertenece a este cliente OAuth.",
            )

        google_user_id = str(token_info.get("sub") or token_info.get("user_id") or "").strip()
        if not google_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No fue posible identificar al usuario de Google.",
            )

        return AuthContext(user_id=google_user_id, access_token=access_token, refresh_token=google_refresh)

    if authorization:
        jwt_token = _extract_bearer_token(authorization)
        if await _token_status(jwt_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT invalidado.",
            )

        payload = await _verify_internal_token(authorization)
        user_id = str(payload.get("id_usuario") or payload.get("sub") or "").strip() or None
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT no contiene el identificador del usuario.",
            )

        return AuthContext(user_id=user_id, access_token=None, refresh_token=google_refresh)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere Authorization o X-Google-Token.",
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
                detail="Debe iniciar sesion con Google (X-Google-Token).",
            )

        return await func(*args, **kwargs)

    return wrapper


