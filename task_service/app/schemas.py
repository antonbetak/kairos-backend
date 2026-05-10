from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


class TareaCrear(BaseModel):
    titulo: str
    descripcion: str | None = None


class TareaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tarea: UUID
    id_usuario: str
    titulo: str
    descripcion: str | None
    completada: bool
    created_at: datetime
    updated_at: datetime
