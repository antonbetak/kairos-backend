from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes.google_calendar import router as google_calendar_router
from app.routes.health import router as health_router


settings = get_settings()

logging.basicConfig(
	level=getattr(logging, settings.log_level.upper(), logging.INFO),
	format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(settings.app_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
	logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
	yield
	logger.info("Stopping %s", settings.app_name)


app = FastAPI(
	title="Kairos Google Calendar Service",
	version="1.0.0",
	description="Standalone Google Calendar integration for listing and managing events.",
	lifespan=lifespan,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.cors_origins_list(),
	allow_credentials=False,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(google_calendar_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
	return {
		"service": settings.app_name,
		"status": "running",
		"docs": "/docs",
		"health": "/health",
		"ready": "/ready",
	}
