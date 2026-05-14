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
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        conexion.close()
        print(f"Evento {routing_key} publicado")
        return True
    except Exception as error:
        print(f"No se pudo publicar {routing_key}: {error}")
        logger.warning("No se pudo publicar %s: %s", routing_key, error)
        return False
