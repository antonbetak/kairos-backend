import json
import logging
import os
from datetime import datetime
from datetime import timezone
from uuid import uuid4

import pika


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"

logger = logging.getLogger(__name__)


def publicar_evento_tarea(
    routing_key: str,
    id_usuario: str,
    id_tarea: str | None = None,
    request_id: str | None = None,
    titulo: str | None = None,
    descripcion: str | None = None,
    error: str | None = None,
    due_at: str | None = None,
    google_access_token: str | None = None,
    google_refresh_token: str | None = None,
    minutes_left: int | None = None,
):
    mensaje = {
        "event_id": str(uuid4()),
        "event_type": routing_key,
        "id_usuario": id_usuario,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if id_tarea:
        mensaje["id_tarea"] = id_tarea
    if request_id:
        mensaje["request_id"] = request_id
    if titulo:
        mensaje["titulo"] = titulo
    if descripcion:
        mensaje["descripcion"] = descripcion
    if error:
        mensaje["error"] = error
    if due_at:
        mensaje["due_at"] = due_at
    if google_access_token:
        mensaje["google_access_token"] = google_access_token
    if google_refresh_token:
        mensaje["google_refresh_token"] = google_refresh_token
    if minutes_left is not None:
        mensaje["minutes_left"] = minutes_left

    try:
        parametros = pika.URLParameters(RABBITMQ_URL)
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()

        canal.exchange_declare(
            exchange=EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        canal.basic_publish(
            exchange=EXCHANGE,
            routing_key=routing_key,
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
            ),
        )
        conexion.close()
        logger.info("Evento %s publicado", routing_key)
        return True
    except Exception as error:
        logger.warning("No se pudo publicar %s: %s", routing_key, error)
        return False


def publicar_tarea_creada(
    id_usuario: str,
    id_tarea: str,
    request_id: str,
    titulo: str,
    descripcion: str | None,
    due_at: str | None = None,
    google_access_token: str | None = None,
    google_refresh_token: str | None = None,
):
    return publicar_evento_tarea(
        "Task.Created",
        id_usuario,
        id_tarea,
        request_id,
        titulo,
        descripcion,
        due_at=due_at,
        google_access_token=google_access_token,
        google_refresh_token=google_refresh_token,
    )


def publicar_tarea_completada(id_usuario: str, id_tarea: str, titulo: str):
    return publicar_evento_tarea(
        "Task.Completed",
        id_usuario=id_usuario,
        id_tarea=id_tarea,
        titulo=titulo,
    )


def publicar_tarea_no_completada(id_usuario: str, id_tarea: str, titulo: str):
    return publicar_evento_tarea(
        "Task.Uncompleted",
        id_usuario=id_usuario,
        id_tarea=id_tarea,
        titulo=titulo,
    )


def publicar_tarea_abandonada(id_usuario: str, id_tarea: str, titulo: str):
    return publicar_evento_tarea(
        "Task.Ditch",
        id_usuario=id_usuario,
        id_tarea=id_tarea,
        titulo=titulo,
    )


def publicar_tarea_error(id_usuario: str, error: str, id_tarea: str | None = None):
    return publicar_evento_tarea(
        "Task.Error",
        id_usuario=id_usuario,
        id_tarea=id_tarea,
        error=error,
    )


def publicar_tarea_due_warning(
    id_usuario: str,
    id_tarea: str,
    titulo: str,
    descripcion: str | None,
    due_at: str,
    minutes_left: int,
):
    return publicar_evento_tarea(
        "Task.DueWarning",
        id_usuario=id_usuario,
        id_tarea=id_tarea,
        titulo=titulo,
        descripcion=descripcion,
        due_at=due_at,
        minutes_left=minutes_left,
    )


def publicar_tarea_vencida(
    id_usuario: str,
    id_tarea: str,
    titulo: str,
    descripcion: str | None,
    due_at: str,
):
    return publicar_evento_tarea(
        "Task.Due",
        id_usuario=id_usuario,
        id_tarea=id_tarea,
        titulo=titulo,
        descripcion=descripcion,
        due_at=due_at,
        minutes_left=0,
    )
