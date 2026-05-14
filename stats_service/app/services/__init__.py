from datetime import date
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EstadisticaUsuario
from app.models import LogroUsuario
from app.models import RachaUsuario
from app.services.notifications_client import crear_notificacion_usuario


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

    crear_notificacion_usuario(
        id_usuario,
        f"Desbloqueaste el logro: {titulo}",
        descripcion,
        "logro",
    )

    return logro


def registrar_tarea_completada(db: Session, id_usuario: UUID):
    estadistica = obtener_o_crear_estadistica_usuario(db, id_usuario)
    racha = obtener_o_crear_racha_usuario(db, id_usuario, "tareas")

    estadistica.tareas_completadas += 1
    estadistica.fecha_actualizacion = datetime.utcnow()

    if estadistica.tareas_creadas > 0:
        estadistica.porcentaje_cumplimiento = (
            estadistica.tareas_completadas / estadistica.tareas_creadas * 100
        )
    else:
        estadistica.porcentaje_cumplimiento = 0

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

    if racha.racha_actual == 3:
        crear_notificacion_usuario(
            id_usuario,
            "Racha activa",
            f"Llevas una racha de {racha.racha_actual} días",
            "racha",
        )

    if racha.racha_actual >= 3:
        desbloquear_logro_si_no_existe(
            db,
            id_usuario,
            "racha_3_tareas",
            "Constancia inicial",
            "Completaste tareas 3 veces consecutivas",
        )

    if estadistica.tareas_creadas > 0 and estadistica.porcentaje_cumplimiento >= 100:
        crear_notificacion_usuario(
            id_usuario,
            "Cumplimiento completo",
            f"Completaste el {round(estadistica.porcentaje_cumplimiento)}% de tus tareas",
            "cumplimiento",
        )

    racha.ultima_fecha_actividad = date.today()

    db.commit()
    db.refresh(estadistica)
    db.refresh(racha)

    return estadistica


def registrar_tarea_creada(db: Session, id_usuario: UUID):
    estadistica = obtener_o_crear_estadistica_usuario(db, id_usuario)

    estadistica.tareas_creadas += 1
    estadistica.fecha_actualizacion = datetime.utcnow()

    if estadistica.tareas_creadas > 0:
        estadistica.porcentaje_cumplimiento = (
            estadistica.tareas_completadas / estadistica.tareas_creadas * 100
        )

    db.commit()
    db.refresh(estadistica)

    return estadistica


def registrar_horario_creado(db: Session, id_usuario: UUID):
    estadistica = obtener_o_crear_estadistica_usuario(db, id_usuario)

    estadistica.horarios_creados += 1
    estadistica.fecha_actualizacion = datetime.utcnow()

    db.commit()
    db.refresh(estadistica)

    return estadistica


def registrar_bloque_completado(db: Session, id_usuario: UUID):
    estadistica = obtener_o_crear_estadistica_usuario(db, id_usuario)

    estadistica.bloques_completados += 1
    estadistica.fecha_actualizacion = datetime.utcnow()

    db.commit()
    db.refresh(estadistica)

    return estadistica
