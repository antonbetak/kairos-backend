import logging

from fastapi import APIRouter, HTTPException

from app.schemas import GenerateRequest, GenerateResponse
from app.services.agent import generar_horario

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Recibe el contexto del usuario (tareas, metas, streaks)
    y devuelve una lista de bloques propuestos para el día.
    Lo llama el schedule-service cuando el usuario pulsa 'Generar'.
    """
    try:
        resultado = await generar_horario(request)
        return resultado
    except Exception as e:
        logger.error("Error inesperado en /generate: %s", e)
        raise HTTPException(status_code=500, detail="Error al generar el horario")