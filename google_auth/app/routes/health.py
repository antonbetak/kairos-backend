from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthResponse


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Healthcheck")
async def healthcheck() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name, environment=settings.app_env)
