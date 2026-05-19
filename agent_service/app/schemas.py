from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCreatedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Task.Created"
    id_usuario: str
    id_tarea: UUID
    titulo: str
    descripcion: str | None = None
    timestamp: datetime


class ScheduleCreatedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Schedule.Created"
    id_usuario: str
    id_bloque: UUID
    titulo: str
    tipo: str | None = None
    status: str | None = None
    timestamp: datetime


class RecommendationRequest(BaseModel):
    id_usuario: UUID
    context: str


class RecommendationEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Agent.RecommendationRequested"
    id_usuario: UUID
    titulo: str
    mensaje: str
    timestamp: datetime


class TareaContexto(BaseModel):
    id: str
    titulo: str
    descripcion: str | None = None
    tipo: str | None = None
    prioridad: str | None = None
    fecha_limite: datetime | None = None
    duracion_estimada_min: int | None = None


class MetaContexto(BaseModel):
    id: str
    titulo: str
    tipo: str | None = None
    progreso_pct: float = 0.0
    fecha_limite: date | None = None


class StreakContexto(BaseModel):
    id: str
    tipo_habito: str
    racha_actual: int
    racha_maxima: int
    ultima_actividad: date | None = None


class GenerateRequest(BaseModel):
    id_usuario: str
    fecha: date
    tareas: list[TareaContexto] = Field(default_factory=list)
    metas: list[MetaContexto] = Field(default_factory=list)
    streaks: list[StreakContexto] = Field(default_factory=list)


TipoBloque = Literal["tarea", "habito", "evento", "libre"]

class BloqueAgente(BaseModel):
    titulo: str
    descripcion: str | None = None
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: TipoBloque
    razon: str | None = None


class GenerateResponse(BaseModel):
    id_usuario: str
    fecha: date
    bloques: list[BloqueAgente]
    es_fallback: bool = False