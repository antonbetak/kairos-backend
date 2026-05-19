import json
import logging
import os
import time
from uuid import UUID
from uuid import uuid4

import pika

from app.db import SessionLocal
from app.models import EventoProcesado
from app.models import NotificacionUsuario
from app.services.idempotency import complete as complete_idempotency
from app.services.idempotency import fail as fail_idempotency
from app.services.idempotency import reserve as reserve_idempotency


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"
QUEUE = "notifications.eventos"
ROUTING_KEYS = [
    "Task.Created",
    "Task.Completed",
    "Task.Ditch",
    "Task.Due",
    "Task.Error",
    "Schedule.Created",
    "Schedule.Updated",
    "Schedule.Error",
    "Task.DueWarning",
    "bloque.completado",
    "notificacion.creada",
    "logro.desbloqueado",
    "racha.actualizada",
]

logger = logging.getLogger(__name__)


def texto_por_defecto(event_type: str):
    if event_type == "Task.Created":
        return "Tarea creada", "Se registró una nueva tarea", "recordatorio"
    if event_type == "Task.Completed":
        return "Tarea completada", "Completaste una tarea", "logro"
    if event_type == "Task.Ditch":
        return "Tarea abandonada", "Una tarea fue descartada", "alerta"
    if event_type == "Task.Error":
        return "Error en tarea", "Ocurrió un problema al procesar una tarea", "alerta"
    if event_type == "Schedule.Created":
        return "Horario creado", "Se creó un nuevo horario", "recordatorio"
    if event_type == "Schedule.Updated":
        return "Horario actualizado", "Tu horario fue actualizado", "recordatorio"
    if event_type == "Schedule.Error":
        return (
            "Error en horario",
            "Ocurrió un problema al procesar un horario",
            "alerta",
        )
    if event_type == "Task.DueWarning":
        return (
            "Tarea próxima a vencer",
            "Tienes una tarea cercana a su vencimiento",
            "recordatorio",
        )
    if event_type == "Task.Due":
        return (
            "Tarea vencida",
            "Una tarea venció y requiere atención",
            "alerta",
        )
    if event_type == "bloque.completado":
        return "Bloque completado", "Completaste un bloque de concentración", "progreso"
    if event_type == "logro.desbloqueado":
        return "Logro desbloqueado", "Desbloqueaste un logro", "logro"
    if event_type == "racha.actualizada":
        return "Racha actualizada", "Tu racha fue actualizada", "racha"
    return "Nueva notificación", "Tienes una nueva notificación", "notificacion"


def _safe_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def crear_notificacion_desde_evento(mensaje: dict):
    event_id = mensaje.get("event_id")
    event_type = mensaje.get("event_type")
    raw_user_id = mensaje.get("id_usuario")

    if not event_id or not event_type or not raw_user_id:
        raise ValueError("Evento incompleto")

    user_id_for_notification = _safe_uuid(str(raw_user_id))
    if user_id_for_notification is None:
        raise ValueError("id_usuario inválido en evento")

    reservation = reserve_idempotency("notifications", event_id)
    if reservation.state == "COMPLETED":
        return

    if reservation.state == "PROCESSING" and not reservation.acquired:
        return

    titulo_default, mensaje_default, tipo_default = texto_por_defecto(event_type)

    notificacion = NotificacionUsuario(
        request_id=_safe_uuid(mensaje.get("request_id")) or uuid4(),
        id_usuario=user_id_for_notification,
        titulo=mensaje.get("titulo") or titulo_default,
        mensaje=mensaje.get("mensaje")
        or mensaje.get("descripcion")
        or mensaje.get("error")
        or mensaje_default,
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
            complete_idempotency("notifications", event_id, {"event_type": event_type})
            return

        notificacion_existente = (
            db.query(NotificacionUsuario)
            .filter(NotificacionUsuario.request_id == notificacion.request_id)
            .first()
            if notificacion.request_id is not None
            else None
        )
        if notificacion_existente:
            complete_idempotency("notifications", event_id, {"event_type": event_type})
            return

        db.add(notificacion)
        db.add(
            EventoProcesado(
                event_id=event_id,
                event_type=event_type,
            )
        )
        db.commit()
        complete_idempotency("notifications", event_id, {"event_type": event_type})
    except Exception:
        db.rollback()
        fail_idempotency("notifications", event_id)
        raise
    finally:
        db.close()


def manejar_mensaje(ch, method, properties, body):
    try:
        mensaje = json.loads(body.decode("utf-8"))
        crear_notificacion_desde_evento(mensaje)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Evento de notificación mal formado: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
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

            logger.info("Consumidor RabbitMQ de notifications iniciado")
            canal.start_consuming()
        except Exception as error:
            logger.warning(
                "No se pudo iniciar consumidor RabbitMQ de notifications: %s", error
            )
            time.sleep(5)
