from datetime import datetime
from datetime import timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import NotificacionUsuario


def crear_notificacion(db: Session, id_usuario: UUID, datos):
    notificacion = NotificacionUsuario(
        id_usuario=id_usuario,
        titulo=datos.titulo,
        mensaje=datos.mensaje,
        tipo=datos.tipo,
    )

    db.add(notificacion)
    db.commit()
    db.refresh(notificacion)

    return notificacion


def obtener_notificaciones_usuario(db: Session, id_usuario: UUID):
    return (
        db.query(NotificacionUsuario)
        .filter(NotificacionUsuario.id_usuario == id_usuario)
        .order_by(NotificacionUsuario.fecha_creacion.desc())
        .all()
    )


def marcar_notificacion_leida(db: Session, notificacion: NotificacionUsuario):
    notificacion.leida = True
    notificacion.fecha_lectura = datetime.now(timezone.utc)

    db.commit()
    db.refresh(notificacion)

    return notificacion


def marcar_todas_como_leidas(db: Session, id_usuario: UUID):
    notificaciones = (
        db.query(NotificacionUsuario)
        .filter(NotificacionUsuario.id_usuario == id_usuario)
        .filter(NotificacionUsuario.leida == False)
        .all()
    )

    fecha_lectura = datetime.now(timezone.utc)
    for notificacion in notificaciones:
        notificacion.leida = True
        notificacion.fecha_lectura = fecha_lectura

    db.commit()

    return obtener_notificaciones_usuario(db, id_usuario)
