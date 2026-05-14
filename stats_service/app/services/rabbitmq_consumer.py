import json
import logging
import os
from datetime import datetime
from datetime import timezone
from uuid import UUID

import pika

from app.db import SessionLocal
from app.models import EventoProcesado
from app.models import EstadisticaUsuario
from app.services.estadisticas import registrar_bloque_completado
from app.services.estadisticas import registrar_tarea_completada


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"
QUEUE = "stats.eventos"
TAREA_COMPLETADA = "tarea.completada"
BLOQUE_COMPLETADO = "bloque.completado"

logger = logging.getLogger(__name__)


def evento_ya_procesado(db, event_id: str):
    return (
        db.query(EventoProcesado)
        .filter(EventoProcesado.event_id == event_id)
        .first()
    )


def guardar_evento_procesado(db, event_id: str, event_type: str):
    evento = EventoProcesado(
        event_id=event_id,
        event_type=event_type,
    )
    db.add(evento)


def fecha_evento(mensaje: dict):
    timestamp = mensaje.get("timestamp")
    if not timestamp:
        return None

    fecha = datetime.fromisoformat(timestamp)
    if fecha.tzinfo:
        fecha = fecha.astimezone(timezone.utc).replace(tzinfo=None)

    return fecha


def ya_llego_por_http(db, id_usuario: UUID, mensaje: dict, campo: str):
    fecha = fecha_evento(mensaje)
    if not fecha:
        return False

    estadistica = (
        db.query(EstadisticaUsuario)
        .filter(EstadisticaUsuario.id_usuario == id_usuario)
        .first()
    )

    if not estadistica or not estadistica.fecha_actualizacion:
        return False

    segundos = abs((fecha - estadistica.fecha_actualizacion).total_seconds())
    return getattr(estadistica, campo) > 0 and segundos <= 10


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
        print("Evento tarea.completada ya procesado")
        return

    if ya_llego_por_http(db, id_usuario, mensaje, "tareas_completadas"):
        guardar_evento_procesado(db, event_id, event_type or TAREA_COMPLETADA)
        db.commit()
        print("Evento tarea.completada ya aplicado por HTTP")
        return

    registrar_tarea_completada(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or TAREA_COMPLETADA)
    db.commit()
    print("Evento tarea.completada recibido en stats")


def procesar_bloque_completado(db, mensaje: dict):
    event_id, event_type, id_usuario = datos_basicos_evento(mensaje)

    if evento_ya_procesado(db, event_id):
        print("Evento bloque.completado ya procesado")
        return

    if ya_llego_por_http(db, id_usuario, mensaje, "bloques_completados"):
        guardar_evento_procesado(db, event_id, event_type or BLOQUE_COMPLETADO)
        db.commit()
        print("Evento bloque.completado ya aplicado por HTTP")
        return

    registrar_bloque_completado(db, id_usuario)
    guardar_evento_procesado(db, event_id, event_type or BLOQUE_COMPLETADO)
    db.commit()
    print("Evento bloque.completado recibido en stats")


def procesar_evento(mensaje: dict):
    event_type = mensaje.get("event_type")
    db = SessionLocal()
    try:
        if event_type == TAREA_COMPLETADA:
            procesar_tarea_completada(db, mensaje)
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
        print(f"Evento mal formado: {error}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
        print(f"No se pudo procesar evento RabbitMQ: {error}")
        logger.warning("No se pudo procesar evento RabbitMQ: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def iniciar_consumidor():
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
            routing_key=TAREA_COMPLETADA,
        )
        canal.queue_bind(
            exchange=EXCHANGE,
            queue=QUEUE,
            routing_key=BLOQUE_COMPLETADO,
        )
        canal.basic_qos(prefetch_count=1)
        canal.basic_consume(
            queue=QUEUE,
            on_message_callback=manejar_mensaje,
        )

        print("Consumidor RabbitMQ de stats iniciado")
        canal.start_consuming()
    except Exception as error:
        print(f"No se pudo iniciar consumidor RabbitMQ: {error}")
        logger.warning("No se pudo iniciar consumidor RabbitMQ: %s", error)
