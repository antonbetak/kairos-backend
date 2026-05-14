import logging
from uuid import UUID

import httpx


NOTIFICATIONS_SERVICE_URL = "http://notifications_service:8000"

logger = logging.getLogger(__name__)


def crear_notificacion_usuario(id_usuario: UUID, titulo: str, mensaje: str, tipo: str):
    try:
        with httpx.Client(timeout=5) as client:
            response = client.post(
                f"{NOTIFICATIONS_SERVICE_URL}/notificaciones/interna",
                json={
                    "id_usuario": str(id_usuario),
                    "titulo": titulo,
                    "mensaje": mensaje,
                    "tipo": tipo,
                },
            )
            if response.status_code >= 400:
                logger.warning("No se pudo crear la notificación: %s", response.text)
    except httpx.RequestError as error:
        logger.warning("No se pudo crear la notificación: %s", error)
