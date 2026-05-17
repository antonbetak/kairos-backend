import json
import logging
from datetime import datetime
from datetime import timezone
from uuid import UUID
from threading import Thread

import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models  # noqa: F401
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
logger = logging.getLogger(__name__)


def _ensure_request_id_column() -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS notificaciones_usuario ADD COLUMN IF NOT EXISTS request_id UUID"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_notificaciones_usuario_request_id ON notificaciones_usuario (request_id)"
        )


def _log_event(event_type: str, status: str, message: str, **fields):
    payload = {
        "request_id": fields.pop("request_id", None),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "notifications_service",
        "event_type": event_type,
        "status": status,
        "message": message,
        "error": fields.pop("error", None),
        **fields,
    }
    logger.info(json.dumps(payload, default=str))


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
    _ensure_request_id_column()
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
    notificacion = crear_notificacion(db, id_usuario, datos, datos.request_id)
    _log_event(
        "NOTIFICATION_CREATED",
        "SUCCESS",
        "Notificación creada correctamente",
        request_id=str(datos.request_id or notificacion.id_notificacion),
        user_id=str(id_usuario),
        notification_id=str(notificacion.id_notificacion),
        trigger_event="manual",
    )
    return notificacion


@app.post("/notificaciones/interna", response_model=NotificacionRespuesta)
def crear_notificacion_interna(
    datos: NotificacionInterna,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    if datos.id_usuario != id_usuario:
        raise HTTPException(status_code=403, detail="No puedes crear notificaciones para otro usuario")

    notificacion = crear_notificacion(db, datos.id_usuario, datos, datos.request_id)
    _log_event(
        "NOTIFICATION_CREATED",
        "SUCCESS",
        "Notificación interna creada correctamente",
        request_id=str(datos.request_id or notificacion.id_notificacion),
        user_id=str(id_usuario),
        notification_id=str(notificacion.id_notificacion),
        trigger_event="internal",
    )
    return notificacion


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
