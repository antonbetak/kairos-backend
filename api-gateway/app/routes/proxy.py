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
		"auth_service": settings.auth_service_url,
		"calendar": settings.calendar_service_url,
		"calendar_service": settings.calendar_service_url,
		"fit": settings.google_fit_url,
		"google_fit": settings.google_fit_url,
		"stt": settings.stt_service_url,
		"stt_service": settings.stt_service_url,
		"notifications": settings.notifications_service_url,
		"notifications_service": settings.notifications_service_url,
		"stats": settings.stats_service_url,
		"stats_service": settings.stats_service_url,
		"agent": settings.agent_service_url,
		"agent_service": settings.agent_service_url,
		"schedule": settings.schedule_service_url,
		"schedule_service": settings.schedule_service_url,
		"task": settings.task_service_url,
		"task_service": settings.task_service_url,
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
		"service": "api-gateway",
		"status": "ok",
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


@router.post("/auth/register")
async def proxy_auth_register(request: Request):
	return await proxy_request(
		request,
		base_url=settings.auth_service_url,
		path="/auth/register",
		timeout=settings.request_timeout_seconds,
	)


@router.post("/auth/login")
async def proxy_auth_login(request: Request):
	return await proxy_request(
		request,
		base_url=settings.auth_service_url,
		path="/auth/login",
		timeout=settings.request_timeout_seconds,
	)


@router.post("/auth/refresh")
async def proxy_auth_refresh(request: Request):
	return await proxy_request(
		request,
		base_url=settings.auth_service_url,
		path="/auth/refresh",
		timeout=settings.request_timeout_seconds,
	)


@router.get("/auth/me")
async def proxy_auth_me(request: Request):
	return await proxy_request(
		request,
		base_url=settings.auth_service_url,
		path="/auth/me",
		timeout=settings.request_timeout_seconds,
	)


@router.get("/auth/verify")
async def proxy_auth_verify(request: Request):
	return await proxy_request(
		request,
		base_url=settings.auth_service_url,
		path="/auth/verify",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/stt/{path:path}", methods=_ALL_METHODS)
async def proxy_stt(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.stt_service_url,
		path=f"/{path}",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/notifications/{path:path}", methods=_ALL_METHODS)
async def proxy_notifications(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.notifications_service_url,
		path=f"/{path}",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/stats/{path:path}", methods=_ALL_METHODS)
async def proxy_stats(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.stats_service_url,
		path=f"/{path}",
		timeout=settings.request_timeout_seconds,
	)


@router.api_route("/agent/{path:path}", methods=_ALL_METHODS)
async def proxy_agent(path: str, request: Request):
	return await proxy_request(
		request,
		base_url=settings.agent_service_url,
		path=f"/{path}",
		timeout=settings.request_timeout_seconds,
	)