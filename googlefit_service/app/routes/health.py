from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthResponse, ReadyResponse


router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse, summary="Healthcheck")
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadyResponse, summary="Readiness check")
async def ready() -> ReadyResponse:
    return ReadyResponse(status="ready", service=settings.app_name)
