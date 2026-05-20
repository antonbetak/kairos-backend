from __future__ import annotations

import json
import logging
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BloqueHorario(BaseModel):
    titulo: str = Field(description="Nombre del bloque")
    descripcion: str | None = Field(default=None, description="Descripción opcional")
    fecha_inicio: str = Field(description="Inicio en formato YYYY-MM-DDTHH:MM:00")
    fecha_fin: str = Field(description="Fin en formato YYYY-MM-DDTHH:MM:00")
    tipo: Literal["tarea", "habito", "evento", "libre"] = Field(
        description=(
            "Tipo exacto del bloque. Usa 'tarea' para estudio, trabajo, proyectos "
            "o actividades productivas. Usa 'habito' para hábitos/streaks. "
            "Usa 'evento' solo para eventos existentes del calendario. "
            "Usa 'libre' solo para descanso, comida o tiempo sin actividad asignada."
        )
    )
    razon: str | None = Field(
        default=None, description="Por qué se propone este bloque en este horario"
    )


class HorarioDia(BaseModel):
    bloques: list[BloqueHorario] = Field(
        description="Lista de bloques del horario del día"
    )


@tool
def generar_horario_dia(bloques: list[dict]) -> str:
    """
    Genera el horario del día con los bloques propuestos.
    Cada bloque debe tener: titulo, fecha_inicio, fecha_fin, tipo.
    Opcionalmente: descripcion y razon.
    """
    try:
        validados = [BloqueHorario(**b) for b in bloques]
        resultado = HorarioDia(bloques=validados)
        return resultado.model_dump_json()
    except Exception as e:
        logger.warning("Error validando bloques: %s", e)
        return json.dumps({"error": str(e), "bloques": []})


class ActualizarMemoria(BaseModel):
    """
    Actualiza uno de los tres tipos de memoria del usuario en ChromaDB.
    Úsala cuando detectes información relevante sobre el usuario que deba recordarse.
    """

    tipo: Literal["semantica", "episodica", "procedimental"] = Field(
        description=(
            "semantica: perfil, metas, hábitos a largo plazo. "
            "episodica: eventos recientes, sueño, actividad. "
            "procedimental: preferencias de horario aprendidas de accept/reject."
        )
    )
    contenido: str = Field(description="Texto descriptivo del patrón o dato a recordar")
