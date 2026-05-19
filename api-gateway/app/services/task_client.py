import httpx

from app.config import get_settings
from app.services.client_utils import error_servicio_caido
from app.services.client_utils import leer_respuesta


settings = get_settings()
TASK_SERVICE_URL = settings.task_service_url.rstrip("/")


def _build_headers(
    authorization: str | None = None,
    x_google_token: str | None = None,
    x_google_refresh: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if authorization:
        headers["Authorization"] = authorization
    if x_google_token:
        headers["X-Google-Token"] = x_google_token
    if x_google_refresh:
        headers["X-Google-Refresh"] = x_google_refresh
    return headers


async def listar_tareas(
    authorization: str,
    x_google_token: str | None = None,
    x_google_refresh: str | None = None,
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TASK_SERVICE_URL}/tasks",
                headers=_build_headers(
                    authorization,
                    x_google_token,
                    x_google_refresh,
                ),
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def crear_tarea(
    authorization: str,
    datos: dict,
    x_google_token: str | None = None,
    x_google_refresh: str | None = None,
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TASK_SERVICE_URL}/tasks",
                headers=_build_headers(
                    authorization,
                    x_google_token,
                    x_google_refresh,
                ),
                json=datos,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def actualizar_tarea(
    authorization: str,
    id_tarea: str,
    datos: dict,
    x_google_token: str | None = None,
    x_google_refresh: str | None = None,
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{TASK_SERVICE_URL}/tasks/{id_tarea}",
                headers=_build_headers(
                    authorization,
                    x_google_token,
                    x_google_refresh,
                ),
                json=datos,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def eliminar_tarea(
    authorization: str,
    id_tarea: str,
    x_google_token: str | None = None,
    x_google_refresh: str | None = None,
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{TASK_SERVICE_URL}/tasks/{id_tarea}",
                headers=_build_headers(
                    authorization,
                    x_google_token,
                    x_google_refresh,
                ),
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)
