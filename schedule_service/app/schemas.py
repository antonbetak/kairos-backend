from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ScheduleCreate(BaseModel):
    titulo: str
    descripcion: str | None = None
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: str | None = None
    status: str = "planned"
    request_id: UUID | None = None


class ScheduleUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    tipo: str | None = None
    status: str | None = None
    request_id: UUID | None = None


class ScheduleGenerateRequest(BaseModel):
    fecha: date
    metas: list[dict] = Field(default_factory=list)
    streaks: list[dict] = Field(default_factory=list)


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID | None
    id_usuario: UUID
    titulo: str
    descripcion: str | None
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: str | None
    status: str
    created_at: datetime
    updated_at: datetime
