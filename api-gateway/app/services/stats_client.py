import httpx

from app.services.client_utils import error_servicio_caido
from app.services.client_utils import leer_respuesta


STATS_SERVICE_URL = "http://stats_service:8000"


async def obtener_estadisticas(id_usuario: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STATS_SERVICE_URL}/estadisticas",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def obtener_racha(id_usuario: str, tipo: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STATS_SERVICE_URL}/rachas/{tipo}",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def listar_logros(id_usuario: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{STATS_SERVICE_URL}/logros",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)
