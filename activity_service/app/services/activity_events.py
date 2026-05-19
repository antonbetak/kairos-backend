from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ActivityEvent


TASK_COMPLETED = "Task.Completed"
BLOCK_COMPLETED = "bloque.completado"
ACHIEVEMENT_UNLOCKED = "logro.desbloqueado"
STREAK_UPDATED = "racha.actualizada"


def _as_uuid(value: object) -> UUID:
    return UUID(str(value))


def _message_for_event(event: dict) -> tuple[str, str, str]:
    event_type = str(event.get("event_type") or "").strip()
    title = str(event.get("titulo") or "").strip()
    description = str(event.get("descripcion") or event.get("mensaje") or "").strip()
    activity_type = str(event.get("tipo") or "").strip()

    if event_type == TASK_COMPLETED:
        task_title = title or "una tarea"
        return (
            "task_completed",
            "Tarea completada",
            f"Completó {task_title}",
        )

    if event_type == BLOCK_COMPLETED:
        block_title = title or "un bloque"
        suffix = f" de {activity_type}" if activity_type else ""
        return (
            "block_completed",
            "Bloque completado",
            f"Completó {block_title}{suffix}",
        )

    if event_type == ACHIEVEMENT_UNLOCKED:
        achievement_title = title or "un logro"
        message = description or f"Desbloqueó {achievement_title}"
        return ("achievement_unlocked", achievement_title, message)

    if event_type == STREAK_UPDATED:
        streak_title = title or "Racha actualizada"
        message = description or "Actualizó su racha"
        return ("streak_updated", streak_title, message)

    return (
        "activity_event",
        title or "Nueva actividad",
        description or "Nueva actividad en Kairos",
    )


def create_event_from_domain_event(db: Session, event: dict) -> ActivityEvent | None:
    source_event_id = str(event.get("event_id") or "").strip()
    event_type = str(event.get("event_type") or "").strip()
    raw_user_id = event.get("id_usuario")

    if not source_event_id or not event_type or not raw_user_id:
        raise ValueError("Evento incompleto")

    existing = (
        db.query(ActivityEvent)
        .filter(ActivityEvent.source_event_id == source_event_id)
        .first()
    )
    if existing:
        return existing

    activity_type, title, message = _message_for_event(event)
    activity = ActivityEvent(
        actor_id=_as_uuid(raw_user_id),
        event_type=activity_type,
        title=title,
        message=message,
        source_service=str(event.get("source_service") or "kairos.events"),
        source_event_id=source_event_id,
        source_entity_id=(
            event.get("id_tarea")
            or event.get("id_bloque")
            or event.get("id_logro")
            or event.get("request_id")
        ),
        visibility="friends",
        extra_data={
            "domain_event_type": event_type,
            "titulo": event.get("titulo"),
            "descripcion": event.get("descripcion"),
            "tipo": event.get("tipo"),
            "status": event.get("status"),
            "timestamp": event.get("timestamp"),
        },
    )

    try:
        db.add(activity)
        db.commit()
        db.refresh(activity)
    except IntegrityError:
        db.rollback()
        return (
            db.query(ActivityEvent)
            .filter(ActivityEvent.source_event_id == source_event_id)
            .first()
        )

    return activity
