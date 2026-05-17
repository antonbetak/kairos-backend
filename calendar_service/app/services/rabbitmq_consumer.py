from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

import pika

from app.config import get_settings
from app.schemas import EventDateTimeInput
from app.services.google_calendar import GoogleCalendarService


RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE = "kairos.events"
QUEUE = "calendar.sync"
TASK_CREATED = "Task.Created"
SCHEDULE_CREATED = "Schedule.Created"

logger = logging.getLogger(__name__)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _calendar_event_window(
    start: datetime | None, end: datetime | None = None
) -> tuple[EventDateTimeInput, EventDateTimeInput]:
    start_dt = start or datetime.now(timezone.utc)
    end_dt = end or (start_dt + timedelta(minutes=30))
    return (
        EventDateTimeInput(date_time=start_dt.isoformat(), time_zone="UTC"),
        EventDateTimeInput(date_time=end_dt.isoformat(), time_zone="UTC"),
    )


def _build_task_event(event: dict[str, Any]) -> dict[str, Any] | None:
    start_dt = _parse_datetime(event.get("due_at")) or _parse_datetime(
        event.get("timestamp")
    )
    start, end = _calendar_event_window(start_dt)
    return {
        "summary": event.get("titulo") or "Kairos Task",
        "description": event.get("descripcion") or "Tarea creada en Kairos",
        "start": start,
        "end": end,
    }


def _build_schedule_event(event: dict[str, Any]) -> dict[str, Any] | None:
    start_dt = _parse_datetime(event.get("fecha_inicio"))
    end_dt = _parse_datetime(event.get("fecha_fin"))
    if not start_dt or not end_dt:
        return None

    start, end = _calendar_event_window(start_dt, end_dt)
    return {
        "summary": event.get("titulo") or "Kairos Schedule",
        "description": event.get("descripcion") or "Horario sincronizado desde Kairos",
        "start": start,
        "end": end,
    }


async def _sync_google_event(event: dict[str, Any]) -> None:
    settings = get_settings()
    service = GoogleCalendarService(settings)

    event_type = event.get("event_type")
    google_access_token = event.get("google_access_token")
    google_refresh_token = event.get("google_refresh_token")

    if event_type == TASK_CREATED:
        payload = _build_task_event(event)
    elif event_type == SCHEDULE_CREATED:
        payload = _build_schedule_event(event)
    else:
        payload = None

    if not payload:
        logger.info("Evento %s ignorado por falta de datos", event_type)
        return

    if not google_access_token:
        logger.warning("Evento %s sin google_access_token; se omite sync", event_type)
        return

    resource = service.build_event_resource(
        payload["summary"],
        payload["description"],
        None,
        payload["start"],
        payload["end"],
        None,
        None,
    )

    try:
        await service.create_event(google_access_token, "primary", resource)
        logger.info("Evento %s sincronizado en Google Calendar", event_type)
    except Exception as error:  # noqa: BLE001
        if google_refresh_token:
            try:
                tokens = await service.refresh_tokens(str(google_refresh_token))
                await service.create_event(tokens.access_token, "primary", resource)
                logger.info("Evento %s sincronizado tras refrescar token", event_type)
                return
            except Exception as refresh_error:  # noqa: BLE001
                logger.warning(
                    "No se pudo sincronizar evento %s tras refrescar token: %s",
                    event_type,
                    refresh_error,
                )
            return

        logger.warning(
            "No se pudo sincronizar evento %s en Google Calendar: %s", event_type, error
        )
        return


def manejar_mensaje(ch, method, properties, body):
    try:
        mensaje = json.loads(body.decode("utf-8"))
        asyncio.run(_sync_google_event(mensaje))
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (json.JSONDecodeError, ValueError) as error:
        logger.warning("Evento mal formado en calendar: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as error:
        logger.warning("No se pudo procesar evento RabbitMQ en calendar: %s", error)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def iniciar_consumidor() -> None:
    while True:
        try:
            parametros = pika.URLParameters(RABBITMQ_URL)
            conexion = pika.BlockingConnection(parametros)
            canal = conexion.channel()

            canal.exchange_declare(
                exchange=EXCHANGE, exchange_type="topic", durable=True
            )
            canal.queue_declare(queue=QUEUE, durable=True)
            for routing_key in (TASK_CREATED, SCHEDULE_CREATED):
                canal.queue_bind(
                    exchange=EXCHANGE, queue=QUEUE, routing_key=routing_key
                )

            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(queue=QUEUE, on_message_callback=manejar_mensaje)

            logger.info("Consumidor RabbitMQ de calendar iniciado")
            canal.start_consuming()
        except Exception as error:
            logger.warning(
                "No se pudo iniciar consumidor RabbitMQ de calendar: %s", error
            )
            time.sleep(5)
