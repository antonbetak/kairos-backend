from datetime import date
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EstadisticaUsuario
from app.models import LogroUsuario
from app.models import RachaUsuario


def obtener_o_crear_estadistica_usuario(db: Session, id_usuario: UUID):
    estadistica = (
        db.query(EstadisticaUsuario)
        .filter(EstadisticaUsuario.id_usuario == id_usuario)
        .first()
    )

    if estadistica:
        return estadistica

    estadistica = EstadisticaUsuario(id_usuario=id_usuario)

    db.add(estadistica)
    db.commit()
    db.refresh(estadistica)

    return estadistica


def obtener_o_crear_racha_usuario(db: Session, id_usuario: UUID, tipo: str):
    racha = (
        db.query(RachaUsuario)
        .filter(RachaUsuario.id_usuario == id_usuario)
        .filter(RachaUsuario.tipo == tipo)
        .first()
    )

    if racha:
        return racha

    racha = RachaUsuario(
        id_usuario=id_usuario,
        tipo=tipo,
        racha_actual=0,
        mejor_racha=0,
    )

    db.add(racha)
    db.commit()
    db.refresh(racha)

    return racha


def listar_logros_usuario(db: Session, id_usuario: UUID):
    return (
        db.query(LogroUsuario)
        .filter(LogroUsuario.id_usuario == id_usuario)
        .order_by(LogroUsuario.fecha_desbloqueo.desc())
        .all()
    )


def desbloquear_logro_si_no_existe(
    db: Session,
    id_usuario: UUID,
    codigo: str,
    titulo: str,
    descripcion: str,
):
    logro = (
        db.query(LogroUsuario)
        .filter(LogroUsuario.id_usuario == id_usuario)
        .filter(LogroUsuario.codigo == codigo)
        .first()
    )

    if logro:
        return logro

    logro = LogroUsuario(
        id_usuario=id_usuario,
        codigo=codigo,
        titulo=titulo,
        descripcion=descripcion,
    )

    db.add(logro)
    db.flush()

    return logro


def registrar_tarea_completada(db: Session, id_usuario: UUID):
    estadistica = obtener_o_crear_estadistica_usuario(db, id_usuario)
    racha = obtener_o_crear_racha_usuario(db, id_usuario, "tareas")

    estadistica.tareas_completadas += 1
    estadistica.fecha_actualizacion = datetime.utcnow()

    if estadistica.tareas_completadas >= 1:
        desbloquear_logro_si_no_existe(
            db,
            id_usuario,
            "primera_tarea",
            "Primer avance",
            "Completaste tu primera tarea en Kairos",
        )

    racha.racha_actual += 1
    if racha.racha_actual > racha.mejor_racha:
        racha.mejor_racha = racha.racha_actual

    racha.ultima_fecha_actividad = date.today()

    db.commit()
    db.refresh(estadistica)
    db.refresh(racha)

    return estadistica
