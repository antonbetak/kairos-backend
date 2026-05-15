import json
import logging
import os
import time
from uuid import UUID

import pika

from app.db import SessionLocal
from app.models import EventoProcesado
from app.models import NotificacionUsuario


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"
QUEUE = "notifications.eventos"
ROUTING_KEYS = [
    "tarea.creada",
    "tarea.completada",
    "tarea.abandonada",
    "tarea.error",
    "horario.creado",
    "horario.actualizado",
    "horario.error",
    "bloque.completado",
    "notificacion.creada",
    "logro.desbloqueado",
    "racha.actualizada",
]

logger = logging.getLogger(__name__)


def texto_por_defecto(event_type: str):
    if event_type == "tarea.creada":
        return "Tarea creada", "Se registró una nueva tarea", "recordatorio"
    if event_type == "tarea.completada":
        return "Tarea completada", "Completaste una tarea", "logro"
    if event_type == "tarea.abandonada":
        return "Tarea abandonada", "Una tarea fue descartada", "alerta"
    if event_type == "tarea.error":
        return "Error en tarea", "Ocurrió un problema al procesar una tarea", "alerta"
    if event_type == "horario.creado":
        return "Horario creado", "Se creó un nuevo horario", "recordatorio"
    if event_type == "horario.actualizado":
        return "Horario actualizado", "Tu horario fue actualizado", "recordatorio"
    if event_type == "horario.error":
        return "Error en horario", "Ocurrió un problema al procesar un horario", "alerta"
    if event_type == "bloque.completado":
        return "Bloque completado", "Completaste un bloque de concentración", "progreso"
    if event_type == "logro.desbloqueado":
        return "Logro desbloqueado", "Desbloqueaste un logro", "logro"
    if event_type == "racha.actualizada":
        return "Racha actualizada", "Tu racha fue actualizada", "racha"
    return "Nueva notificación", "Tienes una nueva notificación", "notificacion"


def crear_notificacion_desde_evento(mensaje: dict):
    event_id = mensaje.get("event_id")
    event_type = mensaje.get("event_type")
    id_usuario = mensaje.get("id_usuario")

    if not event_id or not event_type or not id_usuario:
        raise ValueError("Evento incompleto")

    titulo_default, mensaje_default, tipo_default = texto_por_defecto(event_type)

    notificacion = NotificacionUsuario(
        id_usuario=UUID(str(id_usuario)),
        titulo=mensaje.get("titulo") or titulo_default,
        mensaje=mensaje.get("mensaje") or mensaje.get("descripcion") or mensaje_default,
        tipo=mensaje.get("tipo") or tipo_default,
    )

    db = SessionLocal()
    try:
        evento_procesado = (
            db.query(EventoProcesado)
            .filter(EventoProcesado.event_id == event_id)
            .first()
        )
        if evento_procesado:
            print(f"Evento {event_type} ya procesado en notifications")
            return

        db.add(notificacion)
        db.add(
            EventoProcesado(
                event_id=event_id,
                event_type=event_type,
            )
        )
        db.commit()
        print(f"Notificación guardada por evento {event_type}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def manejar_mensaje(ch, method, properties, body):
    try:
        mensaje = json.loads(body.decode("utf-8"))
        crear_notificacion_desde_evento(mensaje)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, ValueError) as error:
        print(f"Evento de notificación mal formado: {error}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
        print(f"No se pudo procesar evento de notificación: {error}")
        logger.warning("No se pudo procesar evento de notificación: %s", error)
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

            print("Consumidor RabbitMQ de notifications iniciado")
            canal.start_consuming()
        except Exception as error:
            print(f"No se pudo iniciar consumidor RabbitMQ de notifications: {error}")
            logger.warning("No se pudo iniciar consumidor RabbitMQ de notifications: %s", error)
            time.sleep(5)
