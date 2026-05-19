import json
import logging
import time

import pika

from app.config import settings
from app.schemas import TaskCreatedEvent, ScheduleCreatedEvent
from app.services.embedder import (
    registrar_tarea_completada,
    registrar_tarea_abandonada,
    registrar_resumen_estadisticas,
)

logger = logging.getLogger(__name__)

EXCHANGE = "kairos.events"
QUEUE    = "agent.eventos"

CONSUMED_EVENTS = [
    "Task.Created",       # futuro: embedder de tareas nuevas
    "Task.Completed",     # embedder de comportamiento
    "Task.Ditch",         # embedder de abandono
    "Schedule.Created",   # futuro: contexto de horarios generados
    "Stats.SummaryGenerated",  # embedder de resúmenes de productividad
]


def handle_task_created(event: TaskCreatedEvent) -> None:
    # Por ahora no embeddea nada — la tarea aún no tiene comportamiento
    # En el futuro: registrar en ChromaDB que el usuario creó una tarea de X tipo
    logger.info("Task.Created recibido (pendiente embedder): %s", event.titulo)


def handle_schedule_created(event: ScheduleCreatedEvent) -> None:
    # Por ahora no embeddea nada — en el futuro: registrar qué tipo de bloques acepta
    logger.info("Schedule.Created recibido (pendiente embedder): %s", event.titulo)


def _manejar_mensaje(ch, method, properties, body):
    try:
        evento = json.loads(body.decode("utf-8"))
        routing_key = method.routing_key

        if routing_key == "Task.Created":
            handle_task_created(TaskCreatedEvent(**evento))

        elif routing_key == "Task.Completed":
            registrar_tarea_completada(evento)

        elif routing_key == "Task.Ditch":
            registrar_tarea_abandonada(evento)

        elif routing_key == "Schedule.Created":
            handle_schedule_created(ScheduleCreatedEvent(**evento))

        elif routing_key == "Stats.SummaryGenerated":
            registrar_resumen_estadisticas(evento)

        else:
            logger.warning("Routing key no manejada: %s", routing_key)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Evento mal formado en agent: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.warning("Error procesando evento en agent: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def iniciar_consumidor():
    while True:
        try:
            parametros = pika.URLParameters(settings.rabbitmq_url)
            conexion   = pika.BlockingConnection(parametros)
            canal      = conexion.channel()

            canal.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
            canal.queue_declare(queue=QUEUE, durable=True)

            for routing_key in CONSUMED_EVENTS:
                canal.queue_bind(exchange=EXCHANGE, queue=QUEUE, routing_key=routing_key)

            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(queue=QUEUE, on_message_callback=_manejar_mensaje)

            logger.info("Consumidor RabbitMQ del agent iniciado. Escuchando: %s", CONSUMED_EVENTS)
            canal.start_consuming()

        except Exception as e:
            logger.warning("Consumidor caído, reintentando en 5s: %s", e)
            time.sleep(5)