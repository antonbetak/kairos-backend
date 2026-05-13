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
