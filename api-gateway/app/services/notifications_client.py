import httpx

from app.services.client_utils import error_servicio_caido
from app.services.client_utils import leer_respuesta


NOTIFICATIONS_SERVICE_URL = "http://notifications_service:8000"


def _build_headers(authorization: str) -> dict[str, str]:
    return {"Authorization": authorization}


async def listar_notificaciones(authorization: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones",
                headers=_build_headers(authorization),
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def crear_notificacion(authorization: str, data: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones",
                headers=_build_headers(authorization),
                json=data,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def marcar_notificacion_leida(authorization: str, notificacion_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones/{notificacion_id}/leer",
                headers=_build_headers(authorization),
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def marcar_todas_notificaciones_leidas(authorization: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones/leer-todas",
                headers=_build_headers(authorization),
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)
