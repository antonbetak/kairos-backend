from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


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


class GenerateTaskInput(BaseModel):
    id: str
    titulo: str
    tipo: str = "tarea"
    prioridad: str = "media"
    fecha_limite: datetime | None = None
    duracion_estimada_min: int = 60


class GenerateRequest(BaseModel):
    id_usuario: UUID
    fecha: date
    tareas: list[GenerateTaskInput] = Field(default_factory=list)
    metas: list[dict] = Field(default_factory=list)
    streaks: list[dict] = Field(default_factory=list)


class GeneratedBlock(BaseModel):
    titulo: str
    descripcion: str | None = None
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: str = "tarea"
    razon: str | None = None


class GenerateResponse(BaseModel):
    id_usuario: UUID
    fecha: date
    es_fallback: bool = False
    bloques: list[GeneratedBlock]
