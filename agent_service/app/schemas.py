from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


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
