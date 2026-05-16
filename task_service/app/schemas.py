from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class TareaCrear(BaseModel):
    titulo: str
    descripcion: str | None = None
    due_at: datetime | None = None


class TareaActualizar(BaseModel):
    completada: bool
    due_at: datetime | None = None


class TareaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tarea: UUID
    id_usuario: str
    titulo: str
    descripcion: str | None
    completada: bool
    due_at: datetime | None
    due_warning_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime
