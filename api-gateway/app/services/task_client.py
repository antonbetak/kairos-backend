import httpx

from app.config import get_settings
from app.services.client_utils import error_servicio_caido
from app.services.client_utils import leer_respuesta


settings = get_settings()
TASK_SERVICE_URL = settings.task_service_url.rstrip("/")


async def listar_tareas(id_usuario: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TASK_SERVICE_URL}/tasks",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def crear_tarea(id_usuario: str, datos: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TASK_SERVICE_URL}/tasks",
                headers={"X-User-Id": id_usuario},
                json=datos,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def actualizar_tarea(id_usuario: str, id_tarea: str, datos: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{TASK_SERVICE_URL}/tasks/{id_tarea}",
                headers={"X-User-Id": id_usuario},
                json=datos,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def eliminar_tarea(id_usuario: str, id_tarea: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{TASK_SERVICE_URL}/tasks/{id_tarea}",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)
