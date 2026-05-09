from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import EventDateTimeInput, EventReminderInput, GoogleTokenSet


logger = logging.getLogger(__name__)


class GoogleCalendarService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.google_calendar_api_base.rstrip("/")

    async def list_calendars(self, access_token: str) -> dict[str, Any]:
        url = f"{self.base_url}/users/me/calendarList"
        return await self._request("GET", url, access_token)

    async def list_events(
        self,
        access_token: str,
        calendar_id: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.base_url}/calendars/{calendar_id}/events"
        return await self._request("GET", url, access_token, params=params)

    async def create_event(
        self,
        access_token: str,
        calendar_id: str,
        payload: dict[str, Any],
        send_updates: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/calendars/{calendar_id}/events"
        params = {"sendUpdates": send_updates} if send_updates else None
        return await self._request("POST", url, access_token, params=params, json=payload)

    async def update_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
        payload: dict[str, Any],
        send_updates: str | None = None,
    ) -> dict[str, Any]:
        # Google Calendar supports PATCH for partial updates.
        url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}"
        params = {"sendUpdates": send_updates} if send_updates else None
        return await self._request("PATCH", url, access_token, params=params, json=payload)

    async def delete_event(self, access_token: str, calendar_id: str, event_id: str) -> None:
        url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}"
        await self._request("DELETE", url, access_token)

    async def refresh_tokens(self, refresh_token: str) -> GoogleTokenSet:
        payload = {
            "refresh_token": refresh_token,
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(self.settings.google_token_uri, data=payload)

        if response.status_code >= 400:
            logger.warning("Google token refresh failed: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible refrescar el access_token con Google.",
            )

        token_response = response.json()
        access_token = token_response.get("access_token")

        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google no devolvió un access_token válido.",
            )

        return GoogleTokenSet(
            access_token=access_token,
            token_type=str(token_response.get("token_type") or "Bearer"),
            expires_in=token_response.get("expires_in"),
            refresh_token=str(token_response.get("refresh_token") or refresh_token),
            scope=str(token_response.get("scope") or self.settings.google_scope),
            id_token=token_response.get("id_token"),
        )

    def build_event_resource(
        self,
        summary: str | None,
        description: str | None,
        location: str | None,
        start: EventDateTimeInput | None,
        end: EventDateTimeInput | None,
        attendees: list[dict[str, Any]] | None,
        reminders: list[EventReminderInput] | None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {}
        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location

        if start:
            event["start"] = self._normalize_datetime(start)
        if end:
            event["end"] = self._normalize_datetime(end)

        if attendees is not None:
            event["attendees"] = attendees

        if reminders is not None:
            event["reminders"] = {
                "useDefault": False,
                "overrides": [reminder.model_dump(by_alias=True) for reminder in reminders],
            }

        return event

    def _normalize_datetime(self, value: EventDateTimeInput) -> dict[str, Any]:
        if not value.date and not value.date_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start/end debe incluir date o dateTime.",
            )

        payload: dict[str, Any] = {}
        if value.date:
            payload["date"] = value.date
        if value.date_time:
            payload["dateTime"] = value.date_time
        if value.time_zone:
            payload["timeZone"] = value.time_zone
        return payload

    async def _request(
        self,
        method: str,
        url: str,
        access_token: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.request(method, url, headers=headers, params=params, json=json)

        if response.status_code >= 400:
            logger.warning("Google Calendar API failed: %s", response.text)
            raise HTTPException(
                status_code=response.status_code,
                detail="Google Calendar API rechazó la solicitud.",
            )

        if response.status_code == status.HTTP_204_NO_CONTENT or not response.content:
            return {}

        return response.json()
