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


def publicar_evento_schedule(
    routing_key: str,
    id_usuario: str,
    id_bloque: str | None = None,
    titulo: str | None = None,
    descripcion: str | None = None,
    tipo: str | None = None,
    status: str | None = None,
    error: str | None = None,
    id_tarea: str | None = None,
    mensaje_evento: str | None = None,
    fecha_vencimiento: str | None = None,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    google_access_token: str | None = None,
    google_refresh_token: str | None = None,
):
    payload = {
        "event_id": str(uuid4()),
        "event_type": routing_key,
        "id_usuario": id_usuario,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if id_bloque:
        payload["id_bloque"] = id_bloque
    if titulo:
        payload["titulo"] = titulo
    if descripcion:
        payload["descripcion"] = descripcion
    if tipo:
        payload["tipo"] = tipo
    if status:
        payload["status"] = status
    if error:
        payload["error"] = error
    if id_tarea:
        payload["id_tarea"] = id_tarea
    if mensaje_evento:
        payload["mensaje"] = mensaje_evento
    if fecha_vencimiento:
        payload["fecha_vencimiento"] = fecha_vencimiento
    if fecha_inicio:
        payload["fecha_inicio"] = fecha_inicio
    if fecha_fin:
        payload["fecha_fin"] = fecha_fin
    if google_access_token:
        payload["google_access_token"] = google_access_token
    if google_refresh_token:
        payload["google_refresh_token"] = google_refresh_token

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
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                content_type="application/json",
            ),
        )
        conexion.close()
        print(f"Evento {routing_key} publicado")
        logger.info("Evento %s publicado", routing_key)
        return True
    except Exception as error:
        print(f"No se pudo publicar {routing_key}: {error}")
        logger.warning("No se pudo publicar %s: %s", routing_key, error)
        return False


def publicar_horario_creado(
    id_usuario: str,
    id_bloque: str,
    titulo: str,
    descripcion: str | None,
    fecha_inicio: str,
    fecha_fin: str,
    tipo: str | None,
    status: str,
    google_access_token: str | None = None,
    google_refresh_token: str | None = None,
):
    return publicar_evento_schedule(
        "Schedule.Created",
        id_usuario,
        id_bloque,
        titulo,
        descripcion,
        tipo,
        status,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        google_access_token=google_access_token,
        google_refresh_token=google_refresh_token,
    )


def publicar_horario_actualizado(
    id_usuario: str,
    id_bloque: str,
    titulo: str,
    descripcion: str | None,
    fecha_inicio: str,
    fecha_fin: str,
    tipo: str | None,
    status: str,
):
    return publicar_evento_schedule(
        "Schedule.Updated",
        id_usuario,
        id_bloque,
        titulo,
        descripcion,
        tipo,
        status,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


def publicar_horario_error(id_usuario: str, error: str, id_bloque: str | None = None):
    return publicar_evento_schedule(
        "Schedule.Error",
        id_usuario,
        id_bloque,
        error=error,
    )


def publicar_bloque_completado(id_usuario: str, id_bloque: str, titulo: str, tipo: str | None):
    return publicar_evento_schedule(
        routing_key="bloque.completado",
        id_usuario=id_usuario,
        id_bloque=id_bloque,
        titulo=titulo,
        descripcion=None,
        tipo=tipo,
        status="completed",
    )


def publicar_aviso_tarea_vencida(
    id_usuario: str,
    id_tarea: str,
    titulo: str,
    mensaje: str,
    fecha_vencimiento: str | None = None,
):
    return publicar_evento_schedule(
        "Task.DueWarning",
        id_usuario,
        titulo=titulo,
        status="warning",
        id_tarea=id_tarea,
        mensaje=mensaje,
        fecha_vencimiento=fecha_vencimiento,
    )
