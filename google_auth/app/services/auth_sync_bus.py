from __future__ import annotations

import json
import logging
import time
import uuid

import pika
from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import GoogleUserProfile, KairosTokenSet, KairosUserProfile


logger = logging.getLogger(__name__)


class AuthSyncBusClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def sync_google_user(
        self,
        user: GoogleUserProfile,
    ) -> tuple[KairosUserProfile, KairosTokenSet]:
        correlation_id = str(uuid.uuid4())
        response_body: bytes | None = None

        parameters = pika.URLParameters(self.settings.rabbitmq_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        try:
            channel.queue_declare(
                queue=self.settings.auth_google_sync_queue,
                durable=True,
            )
            callback_queue = channel.queue_declare(
                queue="", exclusive=True
            ).method.queue

            def on_response(ch, method, props, body):
                nonlocal response_body
                if props.correlation_id == correlation_id:
                    response_body = body

            channel.basic_consume(
                queue=callback_queue,
                on_message_callback=on_response,
                auto_ack=True,
            )

            payload = {
                "action": "google.sync_user",
                "payload": {
                    "email": user.email,
                    "nombre": user.name,
                    "picture": user.picture,
                    "google_id": user.google_id,
                },
            }

            channel.basic_publish(
                exchange="",
                routing_key=self.settings.auth_google_sync_queue,
                properties=pika.BasicProperties(
                    reply_to=callback_queue,
                    correlation_id=correlation_id,
                    content_type="application/json",
                    delivery_mode=2,
                ),
                body=json.dumps(payload).encode("utf-8"),
            )

            started_at = time.monotonic()
            timeout = max(1.0, float(self.settings.auth_google_sync_timeout_seconds))
            while response_body is None and (time.monotonic() - started_at) < timeout:
                connection.process_data_events(time_limit=0.2)

            if response_body is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No hubo respuesta de auth_service por RabbitMQ.",
                )

            response = json.loads(response_body.decode("utf-8"))
            if not response.get("ok"):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(
                        response.get("error") or "Fallo sincronizando usuario Kairos."
                    ),
                )

            kairos_user = KairosUserProfile.model_validate(
                response.get("kairos_user") or {}
            )
            kairos_tokens = KairosTokenSet.model_validate(
                response.get("kairos_tokens") or {}
            )
            return kairos_user, kairos_tokens
        except pika.exceptions.AMQPError as exc:
            logger.warning("RabbitMQ auth sync failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No fue posible comunicarse con auth_service por RabbitMQ.",
            ) from exc
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass
