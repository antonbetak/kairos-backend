import json
import logging
import time

import pika

from app.config import settings
from app.db import SessionLocal
from app.services.activity_events import ACHIEVEMENT_UNLOCKED
from app.services.activity_events import BLOCK_COMPLETED
from app.services.activity_events import STREAK_UPDATED
from app.services.activity_events import TASK_COMPLETED
from app.services.activity_events import create_event_from_domain_event


EXCHANGE = "kairos.events"
QUEUE = "activity.eventos"
ROUTING_KEYS = [
    TASK_COMPLETED,
    BLOCK_COMPLETED,
    ACHIEVEMENT_UNLOCKED,
    STREAK_UPDATED,
]

logger = logging.getLogger(__name__)


def process_event(event: dict) -> None:
    db = SessionLocal()
    try:
        create_event_from_domain_event(db, event)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def handle_message(ch, method, properties, body):
    try:
        event = json.loads(body.decode("utf-8"))
        process_event(event)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Evento de actividad mal formado: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
        logger.warning("No se pudo procesar evento de actividad: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def start_consumer():
    while True:
        try:
            parameters = pika.URLParameters(settings.rabbitmq_url)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE,
                exchange_type="topic",
                durable=True,
            )
            channel.queue_declare(queue=QUEUE, durable=True)
            for routing_key in ROUTING_KEYS:
                channel.queue_bind(
                    exchange=EXCHANGE,
                    queue=QUEUE,
                    routing_key=routing_key,
                )

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE, on_message_callback=handle_message)

            logger.info("Consumidor RabbitMQ de activity iniciado")
            channel.start_consuming()
        except Exception as error:
            logger.warning(
                "No se pudo iniciar consumidor RabbitMQ de activity: %s", error
            )
            time.sleep(5)
