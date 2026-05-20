from __future__ import annotations

import json
import logging
import time

import pika

from app.config import settings
from app.db.chroma import upsert_documento
from app.schemas import (
    CalendarEventsUpdatedEvent,
    GoogleFitActivityEvent,
    GoogleFitSleepEvent,
    ScheduleBlockAcceptedEvent,
    ScheduleBlockRejectedEvent,
    StatsSummaryEvent,
    TaskCompletedEvent,
    TaskDitchEvent,
)

logger = logging.getLogger(__name__)

EXCHANGE = "kairos.events"
QUEUE = "agent.eventos"

CONSUMED_EVENTS = [
    "Task.Completed",  # → episódica
    "Task.Ditch",  # → episódica
    "Stats.SummaryGenerated",  # → semántica
    "GoogleFit.SleepSynced",  # → episódica
    "GoogleFit.ActivitySynced",  # → episódica
    "Calendar.EventsUpdated",  # → episódica
    "Schedule.BlockAccepted",  # → procedimental
    "Schedule.BlockRejected",  # → procedimental
]


def _handle_task_completed(data: dict) -> None:
    evento = TaskCompletedEvent(**data)
    texto = (
        f"El usuario completó la actividad '{evento.titulo}' de tipo '{evento.tipo}'. "
        f"Estaba programada de {evento.fecha_inicio} a {evento.fecha_fin}. "
        f"Fue completada en: {evento.completada_en or evento.timestamp}."
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_completada_{evento.id_tarea}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "episodica",
            "subtipo": "tarea_completada",
        },
    )


def _handle_task_ditch(data: dict) -> None:
    evento = TaskDitchEvent(**data)
    texto = (
        f"El usuario abandonó la actividad '{evento.titulo}' de tipo '{evento.tipo}'. "
        f"Esto ocurrió el {evento.timestamp}. "
        f"Puede indicar sobrecarga o baja motivación en ese tipo de actividad."
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_abandonada_{evento.id_tarea}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "episodica",
            "subtipo": "tarea_abandonada",
        },
    )


def _handle_stats_summary(data: dict) -> None:
    evento = StatsSummaryEvent(**data)
    tasa = round(
        (evento.completadas / evento.total_actividades * 100)
        if evento.total_actividades > 0
        else 0,
        1,
    )
    texto = (
        f"Resumen {evento.periodo} del usuario (período: {evento.fecha_inicio}): "
        f"Tuvo {evento.total_actividades} actividades, completó {evento.completadas} ({tasa}%). "
        f"Tiempo productivo: {evento.tiempo_productivo_min} minutos. "
        f"Puntuación de productividad: {evento.puntuacion_productividad}/10."
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_resumen_{evento.periodo}_{evento.fecha_inicio}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "semantica",
            "subtipo": "resumen_productividad",
        },
    )


def _handle_googlefit_sleep(data: dict) -> None:
    evento = GoogleFitSleepEvent(**data)
    texto = (
        f"El usuario durmió {evento.duracion_min} minutos la noche del {evento.fecha}. "
        f"Calidad del sueño: {evento.calidad or 'no registrada'}. "
        f"{'Sueño insuficiente — considerar carga ligera al día siguiente.' if evento.duracion_min < 360 else 'Sueño adecuado.'}"
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_sueno_{evento.fecha}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "episodica",
            "subtipo": "sueno",
        },
    )


def _handle_googlefit_activity(data: dict) -> None:
    evento = GoogleFitActivityEvent(**data)
    texto = (
        f"Actividad física del usuario el {evento.fecha}: "
        f"{evento.pasos} pasos, {evento.calorias} calorías quemadas, "
        f"{evento.minutos_activos} minutos activos."
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_actividad_{evento.fecha}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "episodica",
            "subtipo": "actividad_fisica",
        },
    )


def _handle_calendar_events(data: dict) -> None:
    evento = CalendarEventsUpdatedEvent(**data)
    if not evento.eventos:
        return
    eventos_str = "\n".join(
        f"- {e.get('titulo', 'Sin título')} de {e.get('inicio')} a {e.get('fin')}"
        for e in evento.eventos
    )
    texto = (
        f"Eventos de Google Calendar del usuario para el {evento.fecha}:\n{eventos_str}"
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_calendar_{evento.fecha}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "episodica",
            "subtipo": "calendar",
        },
    )


def _handle_block_accepted(data: dict) -> None:
    evento = ScheduleBlockAcceptedEvent(**data)
    texto = (
        f"El usuario aceptó un bloque de tipo '{evento.tipo}' llamado '{evento.titulo}' "
        f"programado de {evento.hora_inicio} a {evento.hora_fin}. "
        f"Esto indica que este tipo de bloque en ese horario le resulta adecuado."
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_aceptado_{evento.id_bloque}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "procedimental",
            "subtipo": "bloque_aceptado",
        },
    )


def _handle_block_rejected(data: dict) -> None:
    evento = ScheduleBlockRejectedEvent(**data)
    texto = (
        f"El usuario rechazó un bloque de tipo '{evento.tipo}' llamado '{evento.titulo}' "
        f"programado de {evento.hora_inicio} a {evento.hora_fin}. "
        f"Esto indica que este tipo de bloque en ese horario NO le resulta adecuado."
    )
    upsert_documento(
        doc_id=f"{evento.id_usuario}_rechazado_{evento.id_bloque}",
        texto=texto,
        metadata={
            "id_usuario": str(evento.id_usuario),
            "tipo_memoria": "procedimental",
            "subtipo": "bloque_rechazado",
        },
    )


HANDLERS = {
    "Task.Completed": _handle_task_completed,
    "Task.Ditch": _handle_task_ditch,
    "Stats.SummaryGenerated": _handle_stats_summary,
    "GoogleFit.SleepSynced": _handle_googlefit_sleep,
    "GoogleFit.ActivitySynced": _handle_googlefit_activity,
    "Calendar.EventsUpdated": _handle_calendar_events,
    "Schedule.BlockAccepted": _handle_block_accepted,
    "Schedule.BlockRejected": _handle_block_rejected,
}


def _manejar_mensaje(ch, method, properties, body):
    try:
        data = json.loads(body.decode("utf-8"))
        routing_key = method.routing_key
        logger.info("Evento recibido: %s", routing_key)

        handler = HANDLERS.get(routing_key)
        if handler:
            handler(data)
        else:
            logger.warning("Routing key no manejada: %s", routing_key)

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Evento mal formado: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    except Exception as e:
        logger.warning("Error procesando evento: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def iniciar_consumidor() -> None:
    """Inicia el consumidor bloqueante en un thread separado."""
    while True:
        try:
            parametros = pika.URLParameters(settings.rabbitmq_url)
            conexion = pika.BlockingConnection(parametros)
            canal = conexion.channel()

            canal.exchange_declare(
                exchange=EXCHANGE,
                exchange_type="topic",
                durable=True,
            )
            canal.queue_declare(queue=QUEUE, durable=True)

            for routing_key in CONSUMED_EVENTS:
                canal.queue_bind(
                    exchange=EXCHANGE,
                    queue=QUEUE,
                    routing_key=routing_key,
                )

            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(
                queue=QUEUE,
                on_message_callback=_manejar_mensaje,
            )

            logger.info(
                "Consumidor RabbitMQ iniciado. Escuchando: %s",
                CONSUMED_EVENTS,
            )
            canal.start_consuming()

        except Exception as e:
            logger.warning("Consumidor caído, reintentando en 5s: %s", e)
            time.sleep(5)
