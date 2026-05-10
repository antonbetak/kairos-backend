import httpx


async def verify_token(token: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://auth_service:8000/auth/verify",
                headers={"Authorization": f"Bearer {token}"},
            )
    except httpx.RequestError:
        return None

    if response.status_code == 200:
        return response.json()

    if response.status_code == 401:
        return None

    return None
