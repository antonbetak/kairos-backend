import httpx
from fastapi import HTTPException


def leer_respuesta(response: httpx.Response):
    try:
        data = response.json()
    except ValueError:
        data = {"detail": response.text or "Respuesta inválida del servicio interno"}

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data


def error_servicio_caido(error: httpx.RequestError):
    raise HTTPException(
        status_code=502,
        detail="No se pudo contactar al servicio interno",
    ) from error
