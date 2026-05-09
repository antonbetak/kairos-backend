from __future__ import annotations

import logging
from functools import wraps

import jwt
from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class AuthContext(BaseModel):
    user_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None


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


def require_auth(
    authorization: str | None = Header(None, description="Bearer JWT interno"),
    google_token: str | None = Header(None, alias="X-Google-Token", description="Google access_token"),
    google_refresh: str | None = Header(None, alias="X-Google-Refresh"),
) -> AuthContext:
    if not authorization and not google_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere Authorization o X-Google-Token.",
        )

    user_id: str | None = None
    if authorization:
        jwt_token = _extract_bearer_token(authorization)

        try:
            payload = jwt.decode(
                jwt_token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                options={"require": ["sub", "exp"]},
            )
        except jwt.PyJWTError as exc:
            logger.warning("JWT validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT inválido o expirado.",
            ) from exc

        user_id = str(payload.get("sub") or "").strip() or None
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT no contiene el identificador del usuario.",
            )

    access_token = str(google_token).strip() if google_token else None

    return AuthContext(user_id=user_id, access_token=access_token, refresh_token=google_refresh)


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


