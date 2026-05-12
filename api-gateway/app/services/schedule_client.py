import httpx

from app.config import get_settings


settings = get_settings()
SCHEDULE_SERVICE_URL = settings.schedule_service_url.rstrip("/")


async def crear_horario(id_usuario: str, datos: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SCHEDULE_SERVICE_URL}/schedule",
            headers={"X-User-Id": id_usuario},
            json=datos,
        )

    return response.json()


async def listar_horarios(id_usuario: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SCHEDULE_SERVICE_URL}/schedule",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def obtener_horario(id_usuario: str, schedule_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{SCHEDULE_SERVICE_URL}/schedule/{schedule_id}",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def actualizar_horario(id_usuario: str, schedule_id: str, datos: dict):
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"{SCHEDULE_SERVICE_URL}/schedule/{schedule_id}",
            headers={"X-User-Id": id_usuario},
            json=datos,
        )

    return response.json()


async def eliminar_horario(id_usuario: str, schedule_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{SCHEDULE_SERVICE_URL}/schedule/{schedule_id}",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()
