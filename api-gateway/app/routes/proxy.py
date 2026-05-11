from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.services.proxy import proxy_request


router = APIRouter(tags=["Gateway"])
settings = get_settings()

_ALL_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def _service_url(service: str) -> str:
	service_map = {
		"google_auth": settings.google_auth_url,
		"auth": settings.google_auth_url,
		"calendar": settings.calendar_service_url,
		"calendar_service": settings.calendar_service_url,
		"fit": settings.google_fit_url,
		"google_fit": settings.google_fit_url,
	}

	if service not in service_map:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Servicio no registrado en el gateway.",
		)

	return service_map[service]


@router.get("/health", summary="Gateway healthcheck")
async def health() -> dict[str, str]:
	return {
		"status": "ok",
		"service": settings.app_name,
		"environment": settings.app_env,
	}


@router.get("/ready", summary="Gateway readiness")
async def ready() -> dict[str, str]:
	return {"status": "ready", "service": settings.app_name}


@router.get("/health/{service}", summary="Service healthcheck via gateway")
async def service_health(service: str, request: Request):
	base_url = _service_url(service)
	return await proxy_request(
		request,
		base_url=base_url,
		path="/health",
		timeout=settings.request_timeout_seconds,
	)


@router.get("/ready/{service}", summary="Service readiness via gateway")
async def service_ready(service: str, request: Request):
	base_url = _service_url(service)
	return await proxy_request(
		request,
		base_url=base_url,
		path="/ready",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/auth/google/{path:path}", methods=_ALL_METHODS)
async def proxy_google_auth(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.google_auth_url,
		path=f"/auth/google/{path}",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/google/{path:path}", methods=_ALL_METHODS)
async def proxy_calendar_google(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.calendar_service_url,
		path=f"/google/{path}",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/device/{path:path}", methods=_ALL_METHODS)
async def proxy_calendar_device(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.calendar_service_url,
		path=f"/device/{path}",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/fit/{path:path}", methods=_ALL_METHODS)
async def proxy_fit(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.google_fit_url,
		path=f"/fit/{path}",
		timeout=settings.request_timeout_seconds,
	)