import httpx


NOTIFICATIONS_SERVICE_URL = "http://notifications_service:8000"


async def listar_notificaciones(id_usuario: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NOTIFICATIONS_SERVICE_URL}/notificaciones",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def crear_notificacion(id_usuario: str, data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NOTIFICATIONS_SERVICE_URL}/notificaciones",
            headers={"X-User-Id": id_usuario},
            json=data,
        )

    return response.json()


async def marcar_notificacion_leida(id_usuario: str, notificacion_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{NOTIFICATIONS_SERVICE_URL}/notificaciones/{notificacion_id}/leer",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()
