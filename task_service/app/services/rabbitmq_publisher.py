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


def publicar_tarea_completada(id_usuario: str, id_tarea: str, titulo: str):
    mensaje = {
        "event_id": str(uuid4()),
        "event_type": "tarea.completada",
        "id_usuario": id_usuario,
        "id_tarea": id_tarea,
        "titulo": titulo,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
            routing_key="tarea.completada",
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        conexion.close()
        print("Evento tarea.completada publicado")
        logger.info("Evento tarea.completada publicado")
    except Exception as error:
        print(f"No se pudo publicar tarea.completada: {error}")
        logger.warning("No se pudo publicar tarea.completada: %s", error)
