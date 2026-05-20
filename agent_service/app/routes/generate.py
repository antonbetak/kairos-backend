from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import APIRouter
from langchain_core.messages import HumanMessage

from app.agent.graph import graph
from app.schemas import BloqueAgente, GenerateRequest, GenerateResponse

router = APIRouter()
logger = logging.getLogger(__name__)

MIN_DOCS_PARA_RAG = 3


def _es_fallback(id_usuario: str) -> bool:
    """Revisa si hay suficiente historial en ChromaDB para usar RAG."""
    from app.db.chroma import contar_documentos_usuario
    return contar_documentos_usuario(id_usuario) < MIN_DOCS_PARA_RAG


def _fallback(request: GenerateRequest) -> GenerateResponse:
    """Heurísticas básicas para usuario nuevo sin historial."""
    from datetime import timedelta

    fecha = request.fecha
    bloques: list[BloqueAgente] = []

    # Hábitos con racha activa primero
    habitos = [s for s in request.streaks if s.racha_actual > 0]
    tareas = sorted(
        request.tareas,
        key=lambda t: t.fecha_limite or datetime(9999, 12, 31),
    )

    slots = [
        (7, 8, "habito"),
        (9, 11, "tarea"),
        (11, 13, "tarea"),
        (15, 17, "tarea"),
        (17, 18, "habito"),
    ]

    items = []
    for h in habitos[:2]:
        items.append(("habito", h.tipo_habito, 30))
    for t in tareas:
        if len(items) >= 5:
            break
        items.append(("tarea", t.titulo, t.duracion_estimada_min or 60))

    for (tipo, titulo, duracion), (h_ini, h_fin, _) in zip(items, slots):
        inicio = datetime(fecha.year, fecha.month, fecha.day, h_ini, 0)
        fin = min(
            inicio + timedelta(minutes=duracion),
            datetime(fecha.year, fecha.month, fecha.day, h_fin, 0),
        )
        bloques.append(BloqueAgente(
            titulo=titulo,
            fecha_inicio=inicio,
            fecha_fin=fin,
            tipo=tipo,
            razon="Horario generado con heurísticas básicas. Mejorará con el tiempo.",
        ))

    return GenerateResponse(
        id_usuario=request.id_usuario,
        fecha=fecha,
        bloques=bloques,
        es_fallback=True,
    )


def _parsear_bloques(messages: list) -> list[BloqueAgente]:
    """Extrae los bloques del último tool call del grafo."""
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            try:
                data = json.loads(msg.content)
                if "bloques" in data:
                    return [BloqueAgente(**b) for b in data["bloques"]]
            except (json.JSONDecodeError, Exception):
                continue
    return []


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Recibe el contexto del usuario y devuelve bloques propuestos para el día.
    Llamado por el schedule-service cuando el usuario pulsa 'Generar'.
    """
    id_usuario = request.id_usuario

    # Usuario nuevo sin historial → fallback
    if _es_fallback(id_usuario):
        logger.info("Usuario %s sin historial suficiente, usando fallback", id_usuario)
        return _fallback(request)

    try:
        config = {
            "configurable": {
                "id_usuario": id_usuario,
                "thread_id": id_usuario,
                "request_data": request.model_dump(mode="json"),
            }
        }

        mensaje_usuario = HumanMessage(
            content=f"Genera el horario del día {request.fecha} para el usuario."
        )

        result = graph.invoke(
            {"messages": [mensaje_usuario]},
            config=config,
        )

        bloques = _parsear_bloques(result["messages"])

        if not bloques:
            logger.warning("Grafo no devolvió bloques para usuario %s, usando fallback", id_usuario)
            return _fallback(request)

        return GenerateResponse(
            id_usuario=id_usuario,
            fecha=request.fecha,
            bloques=bloques,
            es_fallback=False,
        )

    except Exception as e:
        logger.error("Error en grafo LangGraph: %s — usando fallback", e)
        return _fallback(request)