from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.schemas import (
    CalendarListResponse,
    CreateEventRequest,
    DeleteResponse,
    EventItem,
    EventsListResponse,
    GoogleRefreshRequest,
    GoogleRefreshResponse,
    UpdateEventRequest,
)
from app.security import AuthContext, require_auth, require_google_login
from app.services.google_calendar import GoogleCalendarService


router = APIRouter(prefix="/google", tags=["Google Calendar"])
settings = get_settings()


def get_calendar_service() -> GoogleCalendarService:
    return GoogleCalendarService(settings)


@router.get("/calendars", response_model=CalendarListResponse, summary="List user calendars")
@require_google_login
async def list_calendars(
    auth: AuthContext = Depends(require_auth),
    service: GoogleCalendarService = Depends(get_calendar_service),
) -> CalendarListResponse:
    data = await service.list_calendars(auth.access_token)
    return CalendarListResponse.model_validate(data)


@router.get("/events", response_model=EventsListResponse, summary="List events")
@require_google_login
async def list_events(
    calendar_id: str = Query("primary", description="Calendar ID"),
    time_min: str | None = Query(None, description="RFC3339 start time"),
    time_max: str | None = Query(None, description="RFC3339 end time"),
    max_results: int | None = Query(None, ge=1, le=2500),
    page_token: str | None = Query(None),
    q: str | None = Query(None, description="Free text search"),
    single_events: bool = Query(True),
    order_by: str | None = Query(None, description="startTime|updated"),
    auth: AuthContext = Depends(require_auth),
    service: GoogleCalendarService = Depends(get_calendar_service),
) -> EventsListResponse:
    params: dict[str, Any] = {}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    if max_results:
        params["maxResults"] = max_results
    if page_token:
        params["pageToken"] = page_token
    if q:
        params["q"] = q
    if single_events is not None:
        params["singleEvents"] = "true" if single_events else "false"
    if order_by:
        params["orderBy"] = order_by

    data = await service.list_events(auth.access_token, calendar_id, params)
    return EventsListResponse.model_validate(data)


@router.post("/events", response_model=EventItem, status_code=status.HTTP_201_CREATED, summary="Create event")
@require_google_login
async def create_event(
    payload: CreateEventRequest,
    auth: AuthContext = Depends(require_auth),
    service: GoogleCalendarService = Depends(get_calendar_service),
) -> EventItem:
    event_payload = service.build_event_resource(
        summary=payload.summary,
        description=payload.description,
        location=payload.location,
        start=payload.start,
        end=payload.end,
        attendees=[att.model_dump(by_alias=True) for att in payload.attendees or []],
        reminders=payload.reminders,
    )
    data = await service.create_event(
        auth.access_token,
        payload.calendar_id or "primary",
        event_payload,
        send_updates=payload.send_updates,
    )
    return EventItem.model_validate(data)


@router.put("/events/{event_id}", response_model=EventItem, summary="Update event")
@require_google_login
async def update_event(
    event_id: str,
    payload: UpdateEventRequest,
    auth: AuthContext = Depends(require_auth),
    service: GoogleCalendarService = Depends(get_calendar_service),
) -> EventItem:
    if not any(
        [
            payload.summary,
            payload.description,
            payload.location,
            payload.start,
            payload.end,
            payload.attendees is not None,
            payload.reminders is not None,
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay campos para actualizar.",
        )

    event_payload = service.build_event_resource(
        summary=payload.summary,
        description=payload.description,
        location=payload.location,
        start=payload.start,
        end=payload.end,
        attendees=[att.model_dump(by_alias=True) for att in payload.attendees or []]
        if payload.attendees is not None
        else None,
        reminders=payload.reminders,
    )

    data = await service.update_event(
        auth.access_token,
        payload.calendar_id or "primary",
        event_id,
        event_payload,
        send_updates=payload.send_updates,
    )
    return EventItem.model_validate(data)


@router.delete("/events/{event_id}", response_model=DeleteResponse, summary="Delete event")
@require_google_login
async def delete_event(
    event_id: str,
    calendar_id: str = Query("primary"),
    auth: AuthContext = Depends(require_auth),
    service: GoogleCalendarService = Depends(get_calendar_service),
) -> DeleteResponse:
    await service.delete_event(auth.access_token, calendar_id, event_id)
    return DeleteResponse(status="ok", deleted=True)


@router.post("/refresh", response_model=GoogleRefreshResponse, summary="Refresh Google access token")
async def refresh_google_token(
    payload: GoogleRefreshRequest,
    auth: AuthContext = Depends(require_auth),
    service: GoogleCalendarService = Depends(get_calendar_service),
) -> GoogleRefreshResponse:
    tokens = await service.refresh_tokens(payload.refresh_token)
    return GoogleRefreshResponse(tokens=tokens)


