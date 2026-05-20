from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict


TipoTarea = Literal["tarea", "habito", "evento", "libre"]
EstadoTarea = Literal["pendiente", "completada", "abandonada"]


class TareaCrear(BaseModel):
    titulo: str
    descripcion: str | None = None
    due_at: datetime | None = None
    request_id: UUID | None = None
    tipo: TipoTarea | None = None
    prioridad: Literal[0, 1, 2] | None = None
    estado: EstadoTarea | None = None


class TareaActualizar(BaseModel):
    completada: bool | None = None
    due_at: datetime | None = None
    tipo: TipoTarea | None = None
    prioridad: Literal[0, 1, 2] | None = None
    estado: EstadoTarea | None = None


class TareaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_tarea: UUID
    request_id: UUID | None
    id_usuario: str
    titulo: str
    descripcion: str | None
    tipo: TipoTarea
    prioridad: Literal[0, 1, 2]
    estado: EstadoTarea
    completada: bool
    due_at: datetime | None
    due_warning_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime
