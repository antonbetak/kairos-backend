import json
import logging
from datetime import datetime
from datetime import timezone
from fastapi import FastAPI
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx
from uuid import UUID
from uuid import uuid4
from threading import Thread

from app import models
from app.config import settings
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import TareaActualizar
from app.schemas import TareaCrear
from app.schemas import TareaRespuesta
from app.services.idempotency import complete as complete_idempotency
from app.services.idempotency import fail as fail_idempotency
from app.services.idempotency import reserve as reserve_idempotency
from app.services.rabbitmq_publisher import publicar_tarea_abandonada
from app.services.rabbitmq_publisher import publicar_tarea_completada
from app.services.rabbitmq_publisher import publicar_tarea_creada
from app.services.rabbitmq_publisher import publicar_tarea_error
from app.services.due_warning import iniciar_verificador_vencimientos

app = FastAPI(title="Kairos Task Service")
logger = logging.getLogger(__name__)


def _ensure_request_id_column() -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS tareas ADD COLUMN IF NOT EXISTS request_id UUID"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS tareas ADD COLUMN IF NOT EXISTS due_expired_sent_at TIMESTAMPTZ"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_tareas_request_id ON tareas (request_id)"
        )


def _log_event(event_type: str, status: str, message: str, **fields):
    payload = {
        "request_id": fields.pop("request_id", None),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "task_service",
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

    return user_id


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
def create_tables():
    Base.metadata.create_all(bind=engine)
    _ensure_request_id_column()
    Thread(target=iniciar_verificador_vencimientos, daemon=True).start()


@app.get("/health")
def health():
    return {"service": "task_service", "status": "ok"}


@app.get("/tasks", response_model=list[TareaRespuesta])
def listar_tareas(
    id_usuario: str = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    tareas = (
        db.query(models.Tarea)
        .filter(models.Tarea.id_usuario == id_usuario)
        .order_by(models.Tarea.created_at.desc())
        .all()
    )

    return tareas


@app.post("/tasks", response_model=TareaRespuesta)
def crear_tarea(
    tarea: TareaCrear,
    id_usuario: str = Depends(obtener_id_usuario),
    google_tokens: tuple[str | None, str | None] = Depends(obtener_token_google),
    db: Session = Depends(get_db),
):
    request_id = tarea.request_id or uuid4()
    reservation = reserve_idempotency("tasks", request_id)

    if reservation.state == "COMPLETED":
        existente = (
            db.query(models.Tarea)
            .filter(models.Tarea.request_id == request_id)
            .filter(models.Tarea.id_usuario == id_usuario)
            .first()
        )
        if existente:
            _log_event(
                "TASK_CREATED",
                "INFO",
                "Tarea reutilizada desde idempotencia",
                request_id=str(request_id),
                user_id=id_usuario,
                task_id=str(existente.id_tarea),
            )
            return existente

    if reservation.state == "PROCESSING" and not reservation.acquired:
        raise HTTPException(status_code=409, detail="La tarea ya se está procesando")

    existente = (
        db.query(models.Tarea)
        .filter(models.Tarea.request_id == request_id)
        .filter(models.Tarea.id_usuario == id_usuario)
        .first()
    )
    if existente:
        complete_idempotency("tasks", request_id, {"id_tarea": str(existente.id_tarea)})
        _log_event(
            "TASK_CREATED",
            "INFO",
            "Tarea reutilizada desde base de datos",
            request_id=str(request_id),
            user_id=id_usuario,
            task_id=str(existente.id_tarea),
        )
        return existente

    nueva_tarea = models.Tarea(
        request_id=request_id,
        id_usuario=id_usuario,
        titulo=tarea.titulo,
        descripcion=tarea.descripcion,
        completada=False,
        due_at=tarea.due_at,
    )

    try:
        db.add(nueva_tarea)
        db.commit()
        db.refresh(nueva_tarea)
    except IntegrityError:
        db.rollback()
        existente = (
            db.query(models.Tarea)
            .filter(models.Tarea.request_id == request_id)
            .filter(models.Tarea.id_usuario == id_usuario)
            .first()
        )
        if existente:
            complete_idempotency(
                "tasks", request_id, {"id_tarea": str(existente.id_tarea)}
            )
            return existente
        fail_idempotency("tasks", request_id)
        raise
    except Exception as error:
        db.rollback()
        fail_idempotency("tasks", request_id)
        publicar_tarea_error(id_usuario, str(error))
        raise

    complete_idempotency("tasks", request_id, {"id_tarea": str(nueva_tarea.id_tarea)})
    _log_event(
        "TASK_CREATED",
        "SUCCESS",
        "Tarea creada correctamente",
        request_id=str(request_id),
        user_id=id_usuario,
        task_id=str(nueva_tarea.id_tarea),
        source="manual",
    )
    publicar_tarea_creada(
        id_usuario,
        str(nueva_tarea.id_tarea),
        str(request_id),
        nueva_tarea.titulo,
        nueva_tarea.descripcion,
        due_at=nueva_tarea.due_at.isoformat() if nueva_tarea.due_at else None,
        google_access_token=google_tokens[0],
        google_refresh_token=google_tokens[1],
    )

    return nueva_tarea


@app.patch("/tasks/{id_tarea}", response_model=TareaRespuesta)
def actualizar_tarea(
    id_tarea: UUID,
    datos: TareaActualizar,
    id_usuario: str = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    tarea = (
        db.query(models.Tarea)
        .filter(models.Tarea.id_tarea == id_tarea)
        .filter(models.Tarea.id_usuario == id_usuario)
        .first()
    )

    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    estaba_completada = tarea.completada
    try:
        tarea.completada = datos.completada
        if datos.due_at is not None:
            tarea.due_at = datos.due_at
            tarea.due_warning_sent_at = None
        db.commit()
        db.refresh(tarea)
    except Exception as error:
        db.rollback()
        publicar_tarea_error(id_usuario, str(error), str(id_tarea))
        raise

    if not estaba_completada and tarea.completada:
        publicar_tarea_completada(
            id_usuario,
            str(tarea.id_tarea),
            tarea.titulo,
        )

    _log_event(
        "TASK_UPDATED",
        "SUCCESS",
        "Tarea actualizada correctamente",
        request_id=str(getattr(tarea, "request_id", None) or id_tarea),
        user_id=id_usuario,
        task_id=str(tarea.id_tarea),
    )

    return tarea


@app.delete("/tasks/{id_tarea}")
def eliminar_tarea(
    id_tarea: UUID,
    id_usuario: str = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    tarea = (
        db.query(models.Tarea)
        .filter(models.Tarea.id_tarea == id_tarea)
        .filter(models.Tarea.id_usuario == id_usuario)
        .first()
    )

    if not tarea:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    titulo = tarea.titulo
    try:
        db.delete(tarea)
        db.commit()
    except Exception as error:
        db.rollback()
        publicar_tarea_error(id_usuario, str(error), str(id_tarea))
        _log_event(
            "TASK_DELETED",
            "ERROR",
            "No se pudo eliminar la tarea",
            request_id=str(id_tarea),
            user_id=id_usuario,
            task_id=str(id_tarea),
            error=str(error),
        )
        raise

    # El modelo actual no tiene estado "abandonada"; delete representa descarte.
    publicar_tarea_abandonada(id_usuario, str(id_tarea), titulo)
    _log_event(
        "TASK_DELETED",
        "SUCCESS",
        "Tarea eliminada correctamente",
        request_id=str(id_tarea),
        user_id=id_usuario,
        task_id=str(id_tarea),
    )

    return {"message": "Tarea eliminada"}
