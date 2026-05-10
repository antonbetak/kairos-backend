from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class ScheduleCreate(BaseModel):
    titulo: str
    descripcion: str | None = None
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: str | None = None
    status: str = "planned"


class ScheduleUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    tipo: str | None = None
    status: str | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    id_usuario: UUID
    titulo: str
    descripcion: str | None
    fecha_inicio: datetime
    fecha_fin: datetime
    tipo: str | None
    status: str
    created_at: datetime
    updated_at: datetime
