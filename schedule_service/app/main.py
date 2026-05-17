import json
import logging
from fastapi import FastAPI
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx
from uuid import UUID
from uuid import uuid4
from datetime import datetime
from datetime import timezone
from threading import Thread

from app import models
from app.config import settings
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import ScheduleCreate
from app.schemas import ScheduleResponse
from app.schemas import ScheduleUpdate
from app.services.idempotency import complete as complete_idempotency
from app.services.idempotency import fail as fail_idempotency
from app.services.idempotency import reserve as reserve_idempotency
from app.services.rabbitmq_publisher import publicar_bloque_completado
from app.services.rabbitmq_publisher import publicar_horario_actualizado
from app.services.rabbitmq_publisher import publicar_horario_creado
from app.services.rabbitmq_publisher import publicar_horario_error
from app.services.rabbitmq_consumer import iniciar_consumidor

app = FastAPI(title="Kairos Schedule Service")
logger = logging.getLogger(__name__)


def _ensure_request_id_column() -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS schedule_blocks ADD COLUMN IF NOT EXISTS request_id UUID"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_schedule_blocks_request_id ON schedule_blocks (request_id)"
        )


def _log_event(event_type: str, status: str, message: str, **fields):
    payload = {
        "request_id": fields.pop("request_id", None),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "schedule_service",
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


def obtener_id_usuario(authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    try:
        response = httpx.get(
            f"{settings.auth_service_url.rstrip('/')}/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503, detail="No fue posible validar la autorización"
        ) from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    data = response.json()
    user_id = str(data.get("id_usuario") or data.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    return UUID(user_id)


def obtener_token_google(
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
):
    if x_google_token:
        try:
            response = httpx.post(
                f"{settings.auth_service_url.rstrip('/')}/auth/token-status",
                json={"token": x_google_token.strip()},
                timeout=20.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=503, detail="No fue posible validar el token de Google"
            ) from exc

        if response.status_code != 200 or response.json().get("blacklisted"):
            raise HTTPException(status_code=401, detail="Token de Google invalidado")

    return x_google_token, x_google_refresh


@app.on_event("startup")
def crear_tablas():
    Base.metadata.create_all(bind=engine)
    _ensure_request_id_column()
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
    request_id = datos.request_id or uuid4()
    reservation = reserve_idempotency("schedule", request_id)

    if reservation.state == "COMPLETED":
        existente = (
            db.query(models.ScheduleBlock)
            .filter(models.ScheduleBlock.request_id == request_id)
            .filter(models.ScheduleBlock.id_usuario == id_usuario)
            .first()
        )
        if existente:
            _log_event(
                "SCHEDULE_CREATED",
                "INFO",
                "Horario reutilizado desde idempotencia",
                request_id=str(request_id),
                user_id=str(id_usuario),
                schedule_id=str(existente.id),
            )
            return existente

    if reservation.state == "PROCESSING" and not reservation.acquired:
        raise HTTPException(status_code=409, detail="El horario ya se está procesando")

    existente = (
        db.query(models.ScheduleBlock)
        .filter(models.ScheduleBlock.request_id == request_id)
        .filter(models.ScheduleBlock.id_usuario == id_usuario)
        .first()
    )
    if existente:
        complete_idempotency("schedule", request_id, {"schedule_id": str(existente.id)})
        _log_event(
            "SCHEDULE_CREATED",
            "INFO",
            "Horario reutilizado desde base de datos",
            request_id=str(request_id),
            user_id=str(id_usuario),
            schedule_id=str(existente.id),
        )
        return existente

    if datos.fecha_fin <= datos.fecha_inicio:
        raise HTTPException(
            status_code=400, detail="fecha_fin debe ser mayor que fecha_inicio"
        )

    bloque = models.ScheduleBlock(
        request_id=request_id,
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
    except IntegrityError:
        db.rollback()
        existente = (
            db.query(models.ScheduleBlock)
            .filter(models.ScheduleBlock.request_id == request_id)
            .filter(models.ScheduleBlock.id_usuario == id_usuario)
            .first()
        )
        if existente:
            complete_idempotency(
                "schedule", request_id, {"schedule_id": str(existente.id)}
            )
            return existente
        fail_idempotency("schedule", request_id)
        raise
    except Exception as error:
        db.rollback()
        fail_idempotency("schedule", request_id)
        publicar_horario_error(str(id_usuario), str(error))
        raise

    complete_idempotency("schedule", request_id, {"schedule_id": str(bloque.id)})
    _log_event(
        "SCHEDULE_CREATED",
        "SUCCESS",
        "Horario creado correctamente",
        request_id=str(request_id),
        user_id=str(id_usuario),
        schedule_id=str(bloque.id),
        slots_generated=1,
    )
    publicar_horario_creado(
        str(id_usuario),
        str(bloque.id),
        str(request_id),
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

    request_id = datos.request_id or uuid4()
    reservation = reserve_idempotency("schedule", request_id)

    if reservation.state == "COMPLETED" and bloque.request_id == request_id:
        return bloque

    if reservation.state == "PROCESSING" and not reservation.acquired:
        raise HTTPException(
            status_code=409, detail="La actualización ya se está procesando"
        )

    if bloque.request_id == request_id:
        complete_idempotency("schedule", request_id, {"schedule_id": str(bloque.id)})
        _log_event(
            "SCHEDULE_UPDATED",
            "INFO",
            "Horario reutilizado desde idempotencia",
            request_id=str(request_id),
            user_id=str(id_usuario),
            schedule_id=str(bloque.id),
        )
        return bloque

    fecha_inicio = datos.fecha_inicio or bloque.fecha_inicio
    fecha_fin = datos.fecha_fin or bloque.fecha_fin

    if fecha_fin <= fecha_inicio:
        raise HTTPException(
            status_code=400, detail="fecha_fin debe ser mayor que fecha_inicio"
        )

    status_anterior = bloque.status

    try:
        for campo, valor in datos.model_dump(exclude_unset=True).items():
            if campo == "request_id":
                continue
            setattr(bloque, campo, valor)

        bloque.request_id = request_id
        bloque.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(bloque)
    except IntegrityError:
        db.rollback()
        existente = (
            db.query(models.ScheduleBlock)
            .filter(models.ScheduleBlock.request_id == request_id)
            .filter(models.ScheduleBlock.id_usuario == id_usuario)
            .first()
        )
        if existente:
            complete_idempotency(
                "schedule", request_id, {"schedule_id": str(existente.id)}
            )
            return existente
        fail_idempotency("schedule", request_id)
        raise
    except Exception as error:
        db.rollback()
        fail_idempotency("schedule", request_id)
        publicar_horario_error(str(id_usuario), str(error), str(schedule_id))
        _log_event(
            "SCHEDULE_UPDATED",
            "ERROR",
            "No se pudo actualizar el horario",
            request_id=str(request_id),
            user_id=str(id_usuario),
            schedule_id=str(schedule_id),
            error=str(error),
        )
        raise

    if status_anterior != "completed" and bloque.status == "completed":
        publicar_bloque_completado(
            str(id_usuario),
            str(bloque.id),
            bloque.titulo,
            bloque.tipo,
        )

    complete_idempotency("schedule", request_id, {"schedule_id": str(bloque.id)})
    _log_event(
        "SCHEDULE_UPDATED",
        "SUCCESS",
        "Horario actualizado correctamente",
        request_id=str(request_id),
        user_id=str(id_usuario),
        schedule_id=str(bloque.id),
    )
    publicar_horario_actualizado(
        str(id_usuario),
        str(bloque.id),
        str(request_id),
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
