from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class EstadisticaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_estadistica: UUID
    id_usuario: UUID
    tareas_creadas: int
    tareas_completadas: int
    horarios_creados: int
    bloques_completados: int
    porcentaje_cumplimiento: float
    fecha_creacion: datetime
    fecha_actualizacion: datetime


class RachaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_racha: UUID
    id_usuario: UUID
    tipo: str
    racha_actual: int
    mejor_racha: int
    ultima_fecha_actividad: date | None
    fecha_creacion: datetime
    fecha_actualizacion: datetime


class LogroRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_logro: UUID
    id_usuario: UUID
    codigo: str
    titulo: str
    descripcion: str | None
    desbloqueado: bool
    fecha_desbloqueo: datetime
    fecha_creacion: datetime
