import json
import logging
import os
import time
from uuid import UUID

import pika

from app.db import SessionLocal
from app.models import EventoProcesado
from app.services.estadisticas import registrar_bloque_completado
from app.services.estadisticas import registrar_horario_creado
from app.services.estadisticas import registrar_tarea_completada
from app.services.estadisticas import registrar_tarea_creada
from app.services.estadisticas import registrar_tarea_abandonada


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"
QUEUE = "stats.eventos"
TASK_CREATED = "Task.Created"
TASK_COMPLETED = "Task.Completed"
TASK_DITCH = "Task.Ditch"
SCHEDULE_CREATED = "Schedule.Created"
SCHEDULE_UPDATED = "Schedule.Updated"
BLOQUE_COMPLETADO = "bloque.completado"
ROUTING_KEYS = [
    TASK_CREATED,
    TASK_COMPLETED,
    TASK_DITCH,
    SCHEDULE_CREATED,
    SCHEDULE_UPDATED,
    BLOQUE_COMPLETADO,
]

logger = logging.getLogger(__name__)


def evento_ya_procesado(db, event_id: str):
    return (
        db.query(EventoProcesado).filter(EventoProcesado.event_id == event_id).first()
    )


def guardar_evento_procesado(db, event_id: str, event_type: str):
    evento = EventoProcesado(
        event_id=event_id,
        event_type=event_type,
    )
    db.add(evento)


def datos_basicos_evento(mensaje: dict):
    event_id = mensaje.get("event_id")
    event_type = mensaje.get("event_type")
    id_usuario = mensaje.get("id_usuario")

    if not event_id or not id_usuario:
        raise ValueError("Evento incompleto")

    return event_id, event_type, UUID(str(id_usuario))


def procesar_tarea_completada(db, mensaje: dict):
    event_id, event_type, id_usuario = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        logger.debug("Evento Task.Completed ya procesado")
        return

    registrar_tarea_completada(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or TASK_COMPLETED)
    db.commit()
    logger.info("Evento Task.Completed recibido en stats")


def procesar_tarea_creada(db, mensaje: dict):
    event_id, event_type, id_usuario = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        logger.debug("Evento Task.Created ya procesado")
        return

    registrar_tarea_creada(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or TASK_CREATED)
    db.commit()
    logger.info("Evento Task.Created recibido en stats")


def procesar_tarea_abandonada(db, mensaje: dict):
    event_id, event_type, id_usuario = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        logger.debug("Evento Task.Ditch ya procesado")
        return

    registrar_tarea_abandonada(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or TASK_DITCH)
    db.commit()
    logger.info("Evento Task.Ditch recibido en stats")


def procesar_bloque_completado(db, mensaje: dict):
    event_id, event_type, id_usuario = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        logger.debug("Evento bloque.completado ya procesado")
        return

    registrar_bloque_completado(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or BLOQUE_COMPLETADO)
    db.commit()
    logger.info("Evento bloque.completado recibido en stats")


def procesar_horario_creado(db, mensaje: dict):
    event_id, event_type, id_usuario = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        logger.debug("Evento Schedule.Created ya procesado")
        return

    registrar_horario_creado(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or SCHEDULE_CREATED)
    db.commit()
    logger.info("Evento Schedule.Created recibido en stats")


def procesar_horario_actualizado(db, mensaje: dict):
    event_id, event_type, _ = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        logger.debug("Evento Schedule.Updated ya procesado")
        return

    guardar_evento_procesado(db, event_id, event_type or SCHEDULE_UPDATED)
    db.commit()
    logger.info("Evento Schedule.Updated registrado sin cambio de métricas")


def procesar_evento(mensaje: dict):
    event_type = mensaje.get("event_type")
    db = SessionLocal()
    try:
        if event_type == TASK_CREATED:
            procesar_tarea_creada(db, mensaje)
        elif event_type == TASK_COMPLETED:
            procesar_tarea_completada(db, mensaje)
        elif event_type == TASK_DITCH:
            procesar_tarea_abandonada(db, mensaje)
        elif event_type == SCHEDULE_CREATED:
            procesar_horario_creado(db, mensaje)
        elif event_type == SCHEDULE_UPDATED:
            procesar_horario_actualizado(db, mensaje)
        elif event_type == BLOQUE_COMPLETADO:
            procesar_bloque_completado(db, mensaje)
        else:
            raise ValueError("Tipo de evento no soportado")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def manejar_mensaje(ch, method, properties, body):
    try:
        mensaje = json.loads(body.decode("utf-8"))
        procesar_evento(mensaje)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Evento mal formado: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
        logger.warning("No se pudo procesar evento RabbitMQ: %s", error)
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
            for routing_key in ROUTING_KEYS:
                canal.queue_bind(
                    exchange=EXCHANGE,
                    queue=QUEUE,
                    routing_key=routing_key,
                )
            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(
                queue=QUEUE,
                on_message_callback=manejar_mensaje,
            )

            logger.info("Consumidor RabbitMQ de stats iniciado")
            canal.start_consuming()
        except Exception as error:
            logger.warning("No se pudo iniciar consumidor RabbitMQ: %s", error)
            time.sleep(5)
