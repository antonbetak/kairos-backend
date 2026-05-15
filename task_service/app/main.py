from fastapi import FastAPI
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from threading import Thread

from app import models
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import TareaActualizar
from app.schemas import TareaCrear
from app.schemas import TareaRespuesta
from app.services.rabbitmq_publisher import publicar_tarea_abandonada
from app.services.rabbitmq_publisher import publicar_tarea_completada
from app.services.rabbitmq_publisher import publicar_tarea_creada
from app.services.rabbitmq_publisher import publicar_tarea_error
from app.services.due_warning import iniciar_verificador_vencimientos

app = FastAPI(title="Kairos Task Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def obtener_id_usuario(x_user_id: str | None = Header(default=None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    return x_user_id


def obtener_token_google(
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
):
    return x_google_token, x_google_refresh


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
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
    nueva_tarea = models.Tarea(
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
    except Exception as error:
        db.rollback()
        publicar_tarea_error(id_usuario, str(error))
        raise

    publicar_tarea_creada(
        id_usuario,
        str(nueva_tarea.id_tarea),
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
        raise

    # El modelo actual no tiene estado "abandonada"; delete representa descarte.
    publicar_tarea_abandonada(id_usuario, str(id_tarea), titulo)

    return {"message": "Tarea eliminada"}
