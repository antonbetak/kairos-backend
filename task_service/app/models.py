import uuid

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Tarea(Base):
    __tablename__ = "tareas"

    id_tarea = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    request_id = Column(UUID(as_uuid=True), unique=True, nullable=True, index=True)
    id_usuario = Column(String(255), nullable=False, index=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    tipo = Column(String(50), default="libre", nullable=False)
    prioridad = Column(Integer, default=0, nullable=False)
    estado = Column(String(50), default="pendiente", nullable=False)
    completada = Column(Boolean, default=False, nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=True)
    due_warning_sent_at = Column(DateTime(timezone=True), nullable=True)
    due_expired_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
