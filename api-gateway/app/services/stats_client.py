import httpx


STATS_SERVICE_URL = "http://stats_service:8000"


async def obtener_estadisticas(id_usuario: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{STATS_SERVICE_URL}/estadisticas",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def obtener_racha(id_usuario: str, tipo: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{STATS_SERVICE_URL}/rachas/{tipo}",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()


async def listar_logros(id_usuario: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{STATS_SERVICE_URL}/logros",
            headers={"X-User-Id": id_usuario},
        )

    return response.json()
