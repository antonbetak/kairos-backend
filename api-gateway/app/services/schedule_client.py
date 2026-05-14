import httpx

from app.config import get_settings
from app.services.client_utils import error_servicio_caido
from app.services.client_utils import leer_respuesta


settings = get_settings()
SCHEDULE_SERVICE_URL = settings.schedule_service_url.rstrip("/")


async def crear_horario(id_usuario: str, datos: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SCHEDULE_SERVICE_URL}/schedule",
                headers={"X-User-Id": id_usuario},
                json=datos,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def listar_horarios(id_usuario: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SCHEDULE_SERVICE_URL}/schedule",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def obtener_horario(id_usuario: str, schedule_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SCHEDULE_SERVICE_URL}/schedule/{schedule_id}",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def actualizar_horario(id_usuario: str, schedule_id: str, datos: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{SCHEDULE_SERVICE_URL}/schedule/{schedule_id}",
                headers={"X-User-Id": id_usuario},
                json=datos,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def eliminar_horario(id_usuario: str, schedule_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{SCHEDULE_SERVICE_URL}/schedule/{schedule_id}",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)
