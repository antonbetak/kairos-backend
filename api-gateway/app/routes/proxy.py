from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
import logging

from app.config import get_settings
from app.dependencies.auth import obtener_usuario_actual
from app.services.auth_client import get_clerk_id_from_token
from app.services.auth_client import ensure_clerk_user_synced
from app.services.auth_client import is_clerk_token
from app.services.clerk_google_token_service import (
    ClerkGoogleTokenService,
    get_clerk_google_token_service,
)
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
        "activity": settings.activity_service_url,
        "activity_service": settings.activity_service_url,
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


_GOOGLE_ACCESS_TOKEN_HEADER = "X-Google-Access-Token"
_GOOGLE_REFRESH_TOKEN_HEADER = "X-Google-Refresh-Token"
_INTERNAL_TOKEN_HEADER = "X-Internal-Token"
_LEGACY_GOOGLE_TOKEN_HEADERS = {"x-google-token", "x-google-access-token"}
_LEGACY_GOOGLE_REFRESH_HEADERS = {"x-google-refresh", "x-google-refresh-token"}


def _extract_google_headers(request: Request) -> dict[str, str] | None:
    headers: dict[str, str] = {}
    token = (
        request.headers.get(_GOOGLE_ACCESS_TOKEN_HEADER)
        or request.headers.get("X-Google-Token")
    )
    refresh = (
        request.headers.get(_GOOGLE_REFRESH_TOKEN_HEADER)
        or request.headers.get("X-Google-Refresh")
    )
    if token:
        headers[_GOOGLE_ACCESS_TOKEN_HEADER] = token
    if refresh:
        headers[_GOOGLE_REFRESH_TOKEN_HEADER] = refresh
    return headers or None


async def _require_clerk_user(authorization: str | None) -> dict[str, object]:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization with Clerk JWT is required.",
        )

    user = await obtener_usuario_actual(authorization)
    clerk_id = user.get("clerk_id")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk user could not be resolved from the provided token.",
        )
    return user


async def _fetch_google_headers_for_clerk(
    authorization: str | None,
    clerk_service: ClerkGoogleTokenService,
) -> dict[str, str]:
    logger = logging.getLogger("api_gateway.proxy")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Clerk or internal token is required.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header with Clerk or internal token is required.",
        )

    clerk_id: str | None = None
    if is_clerk_token(token):
        clerk_id = await get_clerk_id_from_token(token)
        if not clerk_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Clerk token.",
            )
    else:
        user = await _require_clerk_user(authorization)
        clerk_id = user["clerk_id"]

    logger.debug("Attempting Clerk auth lookup for clerk_id=%s.", clerk_id)
    token_data = await clerk_service.get_google_access_token(clerk_id)

    # Log injection event for testing
    try:
        logger.debug(
            "Injecting %s for clerk_id=%s token=%s refresh=%s",
            _GOOGLE_ACCESS_TOKEN_HEADER,
            clerk_id,
            str(token_data.get("access_token")),
            str(token_data.get("refresh_token")),
        )
    except Exception:
        pass

    headers = {
        _GOOGLE_ACCESS_TOKEN_HEADER: str(token_data["access_token"]),
    }
    refresh_token = token_data.get("refresh_token")
    if refresh_token:
        headers[_GOOGLE_REFRESH_TOKEN_HEADER] = str(refresh_token)

    return headers


@router.api_route("/google/{path:path}", methods=_ALL_METHODS)
async def proxy_calendar_google(
    path: str,
    request: Request,
    authorization: str | None = Header(default=None),
    clerk_service: ClerkGoogleTokenService = Depends(get_clerk_google_token_service),
):
    google_headers = _extract_google_headers(request)
    if google_headers is not None:
        await _require_clerk_user(authorization)
        extra_headers = google_headers
    else:
        extra_headers = await _fetch_google_headers_for_clerk(
            authorization, clerk_service
        )

    if settings.internal_service_token:
        extra_headers[_INTERNAL_TOKEN_HEADER] = settings.internal_service_token

    return await proxy_request(
        request,
        base_url=settings.calendar_service_url,
        path=f"/google/{path}",
        timeout=settings.request_timeout_seconds,
        extra_headers=extra_headers,
    )


@router.api_route("/device/{path:path}", methods=_ALL_METHODS)
async def proxy_calendar_device(path: str, request: Request):
    return await proxy_request(
        request,
        base_url=settings.calendar_service_url,
        path=f"/device/{path}",
        timeout=settings.request_timeout_seconds,
    )


@router.post("/auth/clerk/sync")
async def sync_clerk_user(
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization with Clerk JWT is required.",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token or not is_clerk_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk token.",
        )

    synced_user = await ensure_clerk_user_synced(token)
    if synced_user is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible sincronizar el usuario Clerk.",
        )

    return synced_user


@router.api_route("/fit/{path:path}", methods=_ALL_METHODS)
async def proxy_fit(
    path: str,
    request: Request,
    authorization: str | None = Header(default=None),
    clerk_service: ClerkGoogleTokenService = Depends(get_clerk_google_token_service),
):
    google_headers = _extract_google_headers(request)
    if google_headers is not None:
        await _require_clerk_user(authorization)
        extra_headers = google_headers
    else:
        extra_headers = await _fetch_google_headers_for_clerk(
            authorization, clerk_service
        )

    if settings.internal_service_token:
        extra_headers[_INTERNAL_TOKEN_HEADER] = settings.internal_service_token

    return await proxy_request(
        request,
        base_url=settings.google_fit_url,
        path=f"/fit/{path}",
        timeout=settings.request_timeout_seconds,
        extra_headers=extra_headers,
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


@router.patch("/auth/me/profile")
async def proxy_auth_profile(request: Request):
    return await proxy_request(
        request,
        base_url=settings.auth_service_url,
        path="/auth/me/profile",
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


@router.post("/auth/clerk/exchange")
async def proxy_auth_clerk_exchange(request: Request):
    return await proxy_request(
        request,
        base_url=settings.auth_service_url,
        path="/auth/clerk/exchange",
        timeout=settings.request_timeout_seconds,
    )


@router.get("/auth/users/search")
async def proxy_auth_user_search(request: Request):
    return await proxy_request(
        request,
        base_url=settings.auth_service_url,
        path="/auth/users/search",
        timeout=settings.request_timeout_seconds,
    )


@router.get("/auth/users/{id_usuario}/public")
async def proxy_auth_public_profile(id_usuario: str, request: Request):
    return await proxy_request(
        request,
        base_url=settings.auth_service_url,
        path=f"/auth/users/{id_usuario}/public",
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


@router.api_route("/activity/{path:path}", methods=_ALL_METHODS)
async def proxy_activity(path: str, request: Request):
    return await proxy_request(
        request,
        base_url=settings.activity_service_url,
        path=f"/activity/{path}",
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
