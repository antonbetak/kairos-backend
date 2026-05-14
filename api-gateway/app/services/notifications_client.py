import httpx

from app.services.client_utils import error_servicio_caido
from app.services.client_utils import leer_respuesta


NOTIFICATIONS_SERVICE_URL = "http://notifications_service:8000"


async def listar_notificaciones(id_usuario: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def crear_notificacion(id_usuario: str, data: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones",
                headers={"X-User-Id": id_usuario},
                json=data,
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def marcar_notificacion_leida(id_usuario: str, notificacion_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones/{notificacion_id}/leer",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)


async def marcar_todas_notificaciones_leidas(id_usuario: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones/leer-todas",
                headers={"X-User-Id": id_usuario},
            )
    except httpx.RequestError as error:
        error_servicio_caido(error)

    return leer_respuesta(response)
