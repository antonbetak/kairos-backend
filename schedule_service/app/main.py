from fastapi import FastAPI
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from datetime import timezone
from threading import Thread

from app import models
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import ScheduleCreate
from app.schemas import ScheduleResponse
from app.schemas import ScheduleUpdate
from app.services.rabbitmq_publisher import publicar_bloque_completado
from app.services.rabbitmq_publisher import publicar_horario_actualizado
from app.services.rabbitmq_publisher import publicar_horario_creado
from app.services.rabbitmq_publisher import publicar_horario_error
from app.services.rabbitmq_consumer import iniciar_consumidor

app = FastAPI(title="Kairos Schedule Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def obtener_id_usuario(x_user_id: UUID | None = Header(default=None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    return x_user_id


def obtener_token_google(
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
):
    return x_google_token, x_google_refresh


@app.on_event("startup")
def crear_tablas():
    Base.metadata.create_all(bind=engine)
    Thread(target=iniciar_consumidor, daemon=True).start()


@app.get("/health")
def health():
    return {"service": "schedule-service", "status": "ok"}


@app.post("/schedule", response_model=ScheduleResponse)
def crear_bloque(
    datos: ScheduleCreate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    google_tokens: tuple[str | None, str | None] = Depends(obtener_token_google),
    db: Session = Depends(get_db),
):
    if datos.fecha_fin <= datos.fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin debe ser mayor que fecha_inicio")

    bloque = models.ScheduleBlock(
        id_usuario=id_usuario,
        titulo=datos.titulo,
        descripcion=datos.descripcion,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        tipo=datos.tipo,
        status=datos.status,
    )

    try:
        db.add(bloque)
        db.commit()
        db.refresh(bloque)
    except Exception as error:
        db.rollback()
        publicar_horario_error(str(id_usuario), str(error))
        raise

    publicar_horario_creado(
        str(id_usuario),
        str(bloque.id),
        bloque.titulo,
        bloque.descripcion,
        bloque.fecha_inicio.isoformat(),
        bloque.fecha_fin.isoformat(),
        bloque.tipo,
        bloque.status,
        google_access_token=google_tokens[0],
        google_refresh_token=google_tokens[1],
    )

    return bloque


@app.get("/schedule", response_model=list[ScheduleResponse])
def listar_bloques(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    bloques = (
        db.query(models.ScheduleBlock)
        .filter(models.ScheduleBlock.id_usuario == id_usuario)
        .order_by(models.ScheduleBlock.fecha_inicio.asc())
        .all()
    )

    return bloques


@app.get("/schedule/{schedule_id}", response_model=ScheduleResponse)
def obtener_bloque(
    schedule_id: UUID,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    bloque = (
        db.query(models.ScheduleBlock)
        .filter(models.ScheduleBlock.id == schedule_id)
        .filter(models.ScheduleBlock.id_usuario == id_usuario)
        .first()
    )

    if not bloque:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    return bloque


@app.patch("/schedule/{schedule_id}", response_model=ScheduleResponse)
def actualizar_bloque(
    schedule_id: UUID,
    datos: ScheduleUpdate,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    bloque = (
        db.query(models.ScheduleBlock)
        .filter(models.ScheduleBlock.id == schedule_id)
        .filter(models.ScheduleBlock.id_usuario == id_usuario)
        .first()
    )

    if not bloque:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    fecha_inicio = datos.fecha_inicio or bloque.fecha_inicio
    fecha_fin = datos.fecha_fin or bloque.fecha_fin

    if fecha_fin <= fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_fin debe ser mayor que fecha_inicio")

    status_anterior = bloque.status

    try:
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            setattr(bloque, campo, valor)

        bloque.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bloque)
    except Exception as error:
        db.rollback()
        publicar_horario_error(str(id_usuario), str(error), str(schedule_id))
        raise

    if status_anterior != "completed" and bloque.status == "completed":
        publicar_bloque_completado(
            str(id_usuario),
            str(bloque.id),
            bloque.titulo,
            bloque.tipo,
        )

    publicar_horario_actualizado(
        str(id_usuario),
        str(bloque.id),
        bloque.titulo,
        bloque.descripcion,
        bloque.fecha_inicio.isoformat(),
        bloque.fecha_fin.isoformat(),
        bloque.tipo,
        bloque.status,
    )

    return bloque


@app.delete("/schedule/{schedule_id}")
def eliminar_bloque(
    schedule_id: UUID,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    bloque = (
        db.query(models.ScheduleBlock)
        .filter(models.ScheduleBlock.id == schedule_id)
        .filter(models.ScheduleBlock.id_usuario == id_usuario)
        .first()
    )

    if not bloque:
        raise HTTPException(status_code=404, detail="Bloque no encontrado")

    db.delete(bloque)
    db.commit()

    return {"message": "Bloque eliminado"}
