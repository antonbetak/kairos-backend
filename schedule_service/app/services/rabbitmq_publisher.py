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


def publicar_bloque_completado(id_usuario: str, id_bloque: str, titulo: str, tipo: str | None):
    mensaje = {
        "event_id": str(uuid4()),
        "event_type": "bloque.completado",
        "id_usuario": id_usuario,
        "id_bloque": id_bloque,
        "titulo": titulo,
        "tipo": tipo,
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
            routing_key="bloque.completado",
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
        conexion.close()
        print("Evento bloque.completado publicado")
        logger.info("Evento bloque.completado publicado")
    except Exception as error:
        print(f"No se pudo publicar bloque.completado: {error}")
        logger.warning("No se pudo publicar bloque.completado: %s", error)
