import httpx

from app.config import get_settings


settings = get_settings()


async def verify_token(token: str):
    url = f"{settings.auth_service_url.rstrip('/')}/auth/verify"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        return None

    if response.status_code == 200:
        return response.json()

    if response.status_code == 401:
        return None

    return None
