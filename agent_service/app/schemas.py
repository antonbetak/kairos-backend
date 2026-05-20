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


class TaskCompletedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Task.Completed"
    id_usuario: str
    id_tarea: UUID
    titulo: str
    tipo: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    completada_en: datetime | None = None
    timestamp: datetime


class TaskDitchEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Task.Ditch"
    id_usuario: str
    id_tarea: UUID
    titulo: str
    tipo: str | None = None
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


class ScheduleBlockAcceptedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Schedule.BlockAccepted"
    id_usuario: str
    id_bloque: UUID
    titulo: str
    tipo: str | None = None
    hora_inicio: datetime | None = None
    hora_fin: datetime | None = None
    timestamp: datetime


class ScheduleBlockRejectedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Schedule.BlockRejected"
    id_usuario: str
    id_bloque: UUID
    titulo: str
    tipo: str | None = None
    hora_inicio: datetime | None = None
    hora_fin: datetime | None = None
    timestamp: datetime


class StatsSummaryEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Stats.SummaryGenerated"
    id_usuario: str
    periodo: str
    fecha_inicio: date
    total_actividades: int = 0
    completadas: int = 0
    tiempo_productivo_min: int = 0
    puntuacion_productividad: float = 0.0
    timestamp: datetime


class GoogleFitSleepEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "GoogleFit.SleepSynced"
    id_usuario: str
    fecha: date
    duracion_min: int
    calidad: str | None = None  # 'bueno' | 'regular' | 'malo'
    timestamp: datetime


class GoogleFitActivityEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "GoogleFit.ActivitySynced"
    id_usuario: str
    fecha: date
    pasos: int = 0
    calorias: int = 0
    minutos_activos: int = 0
    timestamp: datetime


class CalendarEventsUpdatedEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Calendar.EventsUpdated"
    id_usuario: str
    fecha: date
    eventos: list[dict] = Field(default_factory=list)
    timestamp: datetime


class RecommendationEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str = "Agent.RecommendationRequested"
    id_usuario: UUID
    titulo: str
    mensaje: str
    timestamp: datetime


class EventoCalendario(BaseModel):
    titulo: str
    inicio: datetime
    fin: datetime
    descripcion: str | None = None


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
    eventos_calendario: list[EventoCalendario] = Field(default_factory=list)


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