from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class NotificacionCrear(BaseModel):
    titulo: str
    mensaje: str
    tipo: str
    request_id: UUID | None = None


class NotificacionInterna(BaseModel):
    id_usuario: UUID
    titulo: str
    mensaje: str
    tipo: str
    request_id: UUID | None = None


class NotificacionRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_notificacion: UUID
    request_id: UUID | None
    id_usuario: UUID
    titulo: str
    mensaje: str
    tipo: str
    leida: bool
    fecha_creacion: datetime
    fecha_lectura: datetime | None
