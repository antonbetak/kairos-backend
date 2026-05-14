import logging

import httpx


STATS_SERVICE_URL = "http://stats_service:8000"

logger = logging.getLogger(__name__)


def notificar_bloque_completado(id_usuario: str):
    try:
        with httpx.Client(timeout=5) as client:
            response = client.post(
                f"{STATS_SERVICE_URL}/eventos/bloque-completado",
                headers={"X-User-Id": id_usuario},
            )
            if response.status_code >= 400:
                logger.warning("No se pudo notificar bloque completado: %s", response.text)
    except httpx.RequestError as error:
        logger.warning("No se pudo notificar bloque completado: %s", error)
