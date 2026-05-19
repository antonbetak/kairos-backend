import uuid
from datetime import datetime

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class EstadisticaUsuario(Base):
    __tablename__ = "estadisticas_usuario"

    id_estadistica = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario = Column(UUID(as_uuid=True), nullable=False, index=True)
    tareas_creadas = Column(Integer, default=0)
    tareas_completadas = Column(Integer, default=0)
    horarios_creados = Column(Integer, default=0)
    bloques_completados = Column(Integer, default=0)
    porcentaje_cumplimiento = Column(Float, default=0)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RachaUsuario(Base):
    __tablename__ = "rachas_usuario"

    id_racha = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario = Column(UUID(as_uuid=True), nullable=False, index=True)
    tipo = Column(String, nullable=False)
    racha_actual = Column(Integer, default=0)
    mejor_racha = Column(Integer, default=0)
    ultima_fecha_actividad = Column(Date, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class LogroUsuario(Base):
    __tablename__ = "logros_usuario"

    id_logro = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    id_usuario = Column(UUID(as_uuid=True), nullable=False, index=True)
    codigo = Column(String, nullable=False)
    titulo = Column(String, nullable=False)
    descripcion = Column(Text, nullable=True)
    desbloqueado = Column(Boolean, default=True)
    fecha_desbloqueo = Column(DateTime, default=datetime.utcnow)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)


class EventoProcesado(Base):
    __tablename__ = "eventos_procesados"

    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
