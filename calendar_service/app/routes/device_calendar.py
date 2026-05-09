from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.schemas import (
    DeviceCalendarsResponse,
    DeviceCalendarsSyncRequest,
    DeviceEventCreateRequest,
    DeviceEventCreateResponse,
    DeviceEventsResponse,
)
from app.security import AuthContext, require_jwt
from app.services.device_calendar import DeviceCalendarService, get_device_calendar_service


router = APIRouter(prefix="/device", tags=["Device Calendar"])


def get_device_service() -> DeviceCalendarService:
    return get_device_calendar_service()


@router.get("/calendars", response_model=DeviceCalendarsResponse, summary="List device calendars")
async def list_device_calendars(
    auth: AuthContext = Depends(require_jwt),
    service: DeviceCalendarService = Depends(get_device_service),
) -> DeviceCalendarsResponse:
    calendars = service.list_calendars(auth.user_id or "")
    return DeviceCalendarsResponse(items=calendars)


@router.post("/calendars", response_model=DeviceCalendarsResponse, summary="Sync device calendars")
async def sync_device_calendars(
    payload: DeviceCalendarsSyncRequest,
    auth: AuthContext = Depends(require_jwt),
    service: DeviceCalendarService = Depends(get_device_service),
) -> DeviceCalendarsResponse:
    calendars = service.set_calendars(auth.user_id or "", payload.calendars)
    return DeviceCalendarsResponse(items=calendars)


@router.get("/events", response_model=DeviceEventsResponse, summary="List device events")
async def list_device_events(
    calendar_id: str | None = Query(None),
    time_min: str | None = Query(None, description="RFC3339 start time"),
    time_max: str | None = Query(None, description="RFC3339 end time"),
    auth: AuthContext = Depends(require_jwt),
    service: DeviceCalendarService = Depends(get_device_service),
) -> DeviceEventsResponse:
    events = service.list_events(auth.user_id or "", calendar_id, time_min, time_max)
    return DeviceEventsResponse(items=events)


@router.post(
    "/events",
    response_model=DeviceEventCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create local device event (client-side)",
)
async def create_device_event(
    payload: DeviceEventCreateRequest,
    auth: AuthContext = Depends(require_jwt),
    service: DeviceCalendarService = Depends(get_device_service),
) -> DeviceEventCreateResponse:
    event = service.create_event(auth.user_id or "", payload)
    return DeviceEventCreateResponse(event=event)
