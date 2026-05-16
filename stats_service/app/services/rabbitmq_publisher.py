import json
import logging
import os
from datetime import datetime
from datetime import timezone
from uuid import UUID
from uuid import uuid4

import pika


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"

logger = logging.getLogger(__name__)


def publicar_evento_notificacion(
    routing_key: str,
    id_usuario: UUID,
    tipo: str,
    titulo: str,
    mensaje: str,
):
    evento = {
        "event_id": str(uuid4()),
        "id_usuario": str(id_usuario),
        "tipo": tipo,
        "titulo": titulo,
        "mensaje": mensaje,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_type": routing_key,
    }

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
            body=json.dumps(evento),
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


def publicar_logro_desbloqueado(id_usuario: UUID, titulo: str, mensaje: str):
    return publicar_evento_notificacion(
        "logro.desbloqueado",
        id_usuario,
        "logro",
        titulo,
        mensaje,
    )


def publicar_racha_actualizada(id_usuario: UUID, titulo: str, mensaje: str):
    return publicar_evento_notificacion(
        "racha.actualizada",
        id_usuario,
        "racha",
        titulo,
        mensaje,
    )


def publicar_notificacion_creada(id_usuario: UUID, titulo: str, mensaje: str, tipo: str):
    return publicar_evento_notificacion(
        "notificacion.creada",
        id_usuario,
        tipo,
        titulo,
        mensaje,
    )
