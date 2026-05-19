from uuid import UUID

import httpx
from fastapi import Header
from fastapi import HTTPException

from app.config import settings


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token invalido o faltante")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token invalido o faltante")

    return token


async def obtener_id_usuario(authorization: str | None = Header(default=None)) -> UUID:
    token = _extract_bearer_token(authorization)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{settings.auth_service_url.rstrip('/')}/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503, detail="No fue posible validar la autorizacion"
        ) from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    data = response.json()
    user_id = str(data.get("id_usuario") or data.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    try:
        return UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID de usuario invalido") from exc
