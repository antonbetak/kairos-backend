from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EstadisticaUsuario


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
