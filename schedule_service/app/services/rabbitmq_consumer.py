import json
import logging
import os
import time

import pika


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"
QUEUE = "schedule.eventos"
TASK_CREATED = "Task.Created"

logger = logging.getLogger(__name__)


def manejar_mensaje(ch, method, properties, body):
    try:
        mensaje = json.loads(body.decode("utf-8"))
        logger.info(
            "Task.Created recibido en schedule: %s",
            mensaje.get("event_id") or mensaje,
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Evento mal formado en schedule: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
        logger.warning("No se pudo procesar evento RabbitMQ en schedule: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def iniciar_consumidor():
    while True:
        try:
            parametros = pika.URLParameters(RABBITMQ_URL)
            conexion = pika.BlockingConnection(parametros)
            canal = conexion.channel()

            canal.exchange_declare(
                exchange=EXCHANGE,
                exchange_type="topic",
                durable=True,
            )
            canal.queue_declare(queue=QUEUE, durable=True)
            canal.queue_bind(
                exchange=EXCHANGE,
                queue=QUEUE,
                routing_key=TASK_CREATED,
            )

            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(
                queue=QUEUE,
                on_message_callback=manejar_mensaje,
            )

            logger.info("Consumidor RabbitMQ de schedule iniciado")
            canal.start_consuming()
        except Exception as error:
            logger.warning(
                "No se pudo iniciar consumidor RabbitMQ de schedule: %s", error
            )
            time.sleep(5)
