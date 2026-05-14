from uuid import UUID

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
from app.schemas import NotificacionRespuesta
from app.services import crear_notificacion
from app.services import marcar_notificacion_leida
from app.services import obtener_notificaciones_usuario

app = FastAPI(title="Kairos Notifications Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def obtener_id_usuario(x_user_id: str | None = Header(default=None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-User-Id inválido")


@app.on_event("startup")
def iniciar_base_de_datos():
    Base.metadata.create_all(bind=engine)


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
