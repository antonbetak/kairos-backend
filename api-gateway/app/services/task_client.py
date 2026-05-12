import httpx

from app.config import get_settings


settings = get_settings()
TASK_SERVICE_URL = settings.task_service_url.rstrip("/")


async def listar_tareas(id_usuario: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TASK_SERVICE_URL}/tasks",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def crear_tarea(id_usuario: str, datos: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TASK_SERVICE_URL}/tasks",
            headers={"X-User-Id": id_usuario},
            json=datos,
        )

    return response.json()
