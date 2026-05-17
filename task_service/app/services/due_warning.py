import logging
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Tarea
from app.services.rabbitmq_publisher import publicar_tarea_due_warning


logger = logging.getLogger(__name__)

WARNING_LEAD_MINUTES = 15
CHECK_INTERVAL_SECONDS = 60


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def verificar_vencimientos_pendientes() -> None:
    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(minutes=WARNING_LEAD_MINUTES)

    db = SessionLocal()
    try:
        tareas = (
            db.execute(
                select(Tarea)
                .where(Tarea.completada.is_(False))
                .where(Tarea.due_at.is_not(None))
                .where(Tarea.due_warning_sent_at.is_(None))
                .where(Tarea.due_at <= limite)
            )
            .scalars()
            .all()
        )

        cambio = False
        for tarea in tareas:
            due_at = _as_utc(tarea.due_at)
            minutes_left = max(0, int((due_at - ahora).total_seconds() // 60))
            publicado = publicar_tarea_due_warning(
                tarea.id_usuario,
                str(tarea.id_tarea),
                tarea.titulo,
                tarea.descripcion,
                due_at=due_at.isoformat(),
                minutes_left=minutes_left,
            )
            if publicado:
                tarea.due_warning_sent_at = ahora
                cambio = True

        if cambio:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def iniciar_verificador_vencimientos() -> None:
    while True:
        try:
            verificar_vencimientos_pendientes()
        except Exception as error:
            logger.warning("No se pudo emitir aviso de vencimientos: %s", error)
        time.sleep(CHECK_INTERVAL_SECONDS)
