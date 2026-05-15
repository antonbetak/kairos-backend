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
    tipo: str | None = None,
    status: str | None = None,
    error: str | None = None,
):
    mensaje = {
        "event_id": str(uuid4()),
        "event_type": routing_key,
        "id_usuario": id_usuario,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if id_bloque:
        mensaje["id_bloque"] = id_bloque
    if titulo:
        mensaje["titulo"] = titulo
    if tipo:
        mensaje["tipo"] = tipo
    if status:
        mensaje["status"] = status
    if error:
        mensaje["error"] = error

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
    tipo: str | None,
    status: str,
):
    return publicar_evento_schedule(
        "horario.creado",
        id_usuario,
        id_bloque,
        titulo,
        tipo,
        status,
    )


def publicar_horario_actualizado(
    id_usuario: str,
    id_bloque: str,
    titulo: str,
    tipo: str | None,
    status: str,
):
    return publicar_evento_schedule(
        "horario.actualizado",
        id_usuario,
        id_bloque,
        titulo,
        tipo,
        status,
    )


def publicar_horario_error(id_usuario: str, error: str, id_bloque: str | None = None):
    return publicar_evento_schedule(
        "horario.error",
        id_usuario,
        id_bloque,
        error=error,
    )


def publicar_bloque_completado(id_usuario: str, id_bloque: str, titulo: str, tipo: str | None):
    return publicar_evento_schedule(
        "bloque.completado",
        id_usuario,
        id_bloque,
        titulo,
        tipo,
        "completed",
    )
