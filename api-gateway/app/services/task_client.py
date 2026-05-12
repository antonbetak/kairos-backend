import httpx


async def listar_tareas(id_usuario: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://task_service:8000/tasks",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def crear_tarea(id_usuario: str, datos: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://task_service:8000/tasks",
            headers={"X-User-Id": id_usuario},
            json=datos,
        )

    return response.json()
