"""RabbitMQ publisher del agent-service.

Publicación de recomendaciones proactivas pendiente de implementar
una vez que el agente tenga suficiente historial por usuario.
"""

from uuid import UUID

PUBLISHED_EVENTS = ["Agent.RecommendationRequested"]


def publish_recommendation_requested(
    id_usuario: UUID,
    titulo: str,
    mensaje: str,
) -> None:
    raise NotImplementedError(
        "Publicación de recomendaciones proactivas pendiente de implementar."
    )