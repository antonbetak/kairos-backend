"""RabbitMQ contracts for future Agent Service RAG flows.

Recommendation publishing is intentionally pending until the agent logic exists.
"""

from uuid import UUID


PUBLISHED_EVENTS = ["Agent.RecommendationRequested"]


def publish_recommendation_requested(
    id_usuario: UUID,
    titulo: str,
    mensaje: str,
) -> None:
    raise NotImplementedError(
        "Lógica RAG pendiente para publicación de recomendaciones"
    )
