from uuid import UUID
from threading import Thread

import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db import Base
from app.db import SessionLocal
from app.db import engine
from app.models import NotificacionUsuario
from app.schemas import NotificacionCrear
from app.schemas import NotificacionInterna
from app.schemas import NotificacionRespuesta
from app.services.notificaciones import crear_notificacion
from app.services.notificaciones import marcar_notificacion_leida
from app.services.notificaciones import marcar_todas_como_leidas
from app.services.notificaciones import obtener_notificaciones_usuario
from app.services.rabbitmq_consumer import iniciar_consumidor
from app.config import settings

app = FastAPI(title="Kairos Notifications Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    return token


async def obtener_id_usuario(authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{settings.auth_service_url.rstrip('/')}/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="No fue posible validar la autorización") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    data = response.json()
    user_id = str(data.get("id_usuario") or data.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


@app.on_event("startup")
def iniciar_base_de_datos():
    Base.metadata.create_all(bind=engine)
    Thread(target=iniciar_consumidor, daemon=True).start()


@app.get("/health")
def health():
    return {"service": "notifications_service", "status": "ok"}


@app.get("/notificaciones", response_model=list[NotificacionRespuesta])
def listar_notificaciones(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return obtener_notificaciones_usuario(db, id_usuario)


@app.post("/notificaciones", response_model=NotificacionRespuesta)
def crear_nueva_notificacion(
    datos: NotificacionCrear,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return crear_notificacion(db, id_usuario, datos)


@app.post("/notificaciones/interna", response_model=NotificacionRespuesta)
def crear_notificacion_interna(
    datos: NotificacionInterna,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    if datos.id_usuario != id_usuario:
        raise HTTPException(status_code=403, detail="No puedes crear notificaciones para otro usuario")

    return crear_notificacion(db, datos.id_usuario, datos)


@app.patch("/notificaciones/{notificacion_id}/leer", response_model=NotificacionRespuesta)
def leer_notificacion(
    notificacion_id: UUID,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    notificacion = (
        db.query(NotificacionUsuario)
        .filter(NotificacionUsuario.id_notificacion == notificacion_id)
        .first()
    )

    if not notificacion:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    if notificacion.id_usuario != id_usuario:
        raise HTTPException(status_code=403, detail="No puedes modificar esta notificación")

    return marcar_notificacion_leida(db, notificacion)


@app.patch("/notificaciones/leer-todas", response_model=list[NotificacionRespuesta])
def leer_todas_notificaciones(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return marcar_todas_como_leidas(db, id_usuario)
