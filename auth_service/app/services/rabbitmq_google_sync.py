from __future__ import annotations

import json
import logging
import re
import secrets
import time
import unicodedata
from datetime import datetime
from datetime import timezone
from uuid import UUID

import pika
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models
from app.config import settings
from app.database import SessionLocal
from app.security import create_access_token
from app.security import create_refresh_token
from app.security import create_token_session_id


logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
HANDLE_PATTERN = re.compile(r"[^a-z0-9_.]+")


def _slugify_handle(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )
    normalized = normalized.removeprefix("@")
    normalized = HANDLE_PATTERN.sub("_", normalized)
    normalized = re.sub(r"[_\\.]{2,}", "_", normalized).strip("_.")
    return normalized[:60] or "usuario"


def _generate_unique_handle(db, nombre: str, email: str) -> str:
    email_prefix = str(email).split("@", 1)[0]
    base = _slugify_handle(email_prefix or nombre)
    handle = base
    suffix = 2
    while db.execute(select(models.User).where(models.User.handle == handle)).first():
        suffix_text = str(suffix)
        max_base_length = max(1, 60 - len(suffix_text))
        handle = f"{base[:max_base_length]}{suffix_text}"
        suffix += 1
    return handle


def _serialize_user(user: models.User) -> dict[str, str | None]:
    return {
        "id_usuario": str(user.id_usuario),
        "nombre": user.nombre,
        "email": user.email,
        "handle": user.handle,
        "avatar_url": user.avatar_url,
    }


def _serialize_tokens(tokens: dict[str, object]) -> dict[str, object]:
    return {
        "access_token": str(tokens["access_token"]),
        "refresh_token": str(tokens["refresh_token"]),
        "token_type": "bearer",
        "expires_in": int(tokens["expires_in"]),
        "refresh_expires_in": int(tokens["refresh_expires_in"]),
    }


def _sync_google_user(payload: dict[str, object]) -> dict[str, object]:
    email = str(payload.get("email") or "").strip().lower()
    nombre = str(payload.get("nombre") or "").strip()
    picture = payload.get("picture")
    clerk_id = str(payload.get("clerk_id") or "").strip() or None

    if not email:
        raise ValueError("email es requerido")

    if not nombre:
        nombre = email.split("@", 1)[0] or "Usuario Kairos"

    db = SessionLocal()
    try:
        user = db.execute(
            select(models.User).where(models.User.email == email)
        ).scalar_one_or_none()

        if user:
            updates = False
            picture_value = str(picture).strip() if picture else None
            if picture_value and user.avatar_url != picture_value:
                user.avatar_url = picture_value
                updates = True
            if clerk_id and not user.clerk_id:
                user.clerk_id = clerk_id
                updates = True
            if not user.handle:
                user.handle = _generate_unique_handle(db, user.nombre, user.email)
                updates = True
            if updates:
                db.commit()
                db.refresh(user)
        else:
            user = models.User(
                nombre=nombre,
                email=email,
                clerk_id=clerk_id,
                handle=_generate_unique_handle(db, nombre, email),
                avatar_url=str(picture).strip() if picture else None,
                password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = db.execute(
                    select(models.User).where(models.User.email == email)
                ).scalar_one_or_none()
                if user is None:
                    raise
            db.refresh(user)

        session_id = create_token_session_id()
        access_token, expires_in = create_access_token(
            user_id=UUID(str(user.id_usuario)),
            email=user.email,
            session_id=session_id,
        )
        refresh_token, refresh_expires_in = create_refresh_token(
            user_id=UUID(str(user.id_usuario)),
            email=user.email,
            session_id=session_id,
        )

        return {
            "ok": True,
            "kairos_user": _serialize_user(user),
            "kairos_tokens": _serialize_tokens(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in,
                    "refresh_expires_in": refresh_expires_in,
                }
            ),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        db.close()


def _handle_message(channel, method, properties, body):
    reply_to = properties.reply_to
    correlation_id = properties.correlation_id

    response_payload: dict[str, object]
    try:
        message = json.loads(body.decode("utf-8"))
        action = str(message.get("action") or "").strip()

        if action != "google.sync_user":
            raise ValueError("accion no soportada")

        payload = message.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("payload invalido")

        response_payload = _sync_google_user(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error procesando sync google user: %s", exc)
        response_payload = {"ok": False, "error": str(exc)}

    if reply_to and correlation_id:
        channel.basic_publish(
            exchange="",
            routing_key=reply_to,
            body=json.dumps(response_payload).encode("utf-8"),
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                content_type="application/json",
            ),
        )

    channel.basic_ack(delivery_tag=method.delivery_tag)


def start_google_sync_consumer() -> None:
    queue_name = settings.google_sync_queue

    while True:
        try:
            parameters = pika.URLParameters(settings.rabbitmq_url)
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()

            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_qos(prefetch_count=8)
            channel.basic_consume(queue=queue_name, on_message_callback=_handle_message)

            logger.info("RabbitMQ consumer de auth sync iniciado en %s", queue_name)
            channel.start_consuming()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fallo consumidor RabbitMQ auth sync: %s", exc)
            time.sleep(5)
