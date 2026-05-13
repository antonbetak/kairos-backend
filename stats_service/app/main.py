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
from app.schemas import EstadisticaRespuesta
from app.schemas import LogroRespuesta
from app.schemas import RachaRespuesta
from app.services import obtener_o_crear_estadistica_usuario
from app.services import obtener_o_crear_racha_usuario
from app.services import listar_logros_usuario
from app.services import registrar_bloque_completado
from app.services import registrar_horario_creado
from app.services import registrar_tarea_completada
from app.services import registrar_tarea_creada

app = FastAPI(title="Kairos Stats Service")


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
    return {"service": "stats_service", "status": "ok"}


@app.get("/estadisticas", response_model=EstadisticaRespuesta)
def obtener_estadisticas(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return obtener_o_crear_estadistica_usuario(db, id_usuario)


@app.get("/rachas/{tipo}", response_model=RachaRespuesta)
def obtener_racha(
    tipo: str,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return obtener_o_crear_racha_usuario(db, id_usuario, tipo)


@app.get("/logros", response_model=list[LogroRespuesta])
def listar_logros(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return listar_logros_usuario(db, id_usuario)


@app.post("/eventos/tarea-completada", response_model=EstadisticaRespuesta)
def registrar_evento_tarea_completada(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return registrar_tarea_completada(db, id_usuario)


@app.post("/eventos/tarea-creada", response_model=EstadisticaRespuesta)
def registrar_evento_tarea_creada(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return registrar_tarea_creada(db, id_usuario)


@app.post("/eventos/horario-creado", response_model=EstadisticaRespuesta)
def registrar_evento_horario_creado(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return registrar_horario_creado(db, id_usuario)


@app.post("/eventos/bloque-completado", response_model=EstadisticaRespuesta)
def registrar_evento_bloque_completado(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return registrar_bloque_completado(db, id_usuario)
