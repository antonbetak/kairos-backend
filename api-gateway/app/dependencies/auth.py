from fastapi import Header
from fastapi import HTTPException

from app.services.auth_client import verify_token


async def obtener_usuario_actual(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    usuario = await verify_token(token)
    if not usuario:
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    return usuario
