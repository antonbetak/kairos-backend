from __future__ import annotations

import logging
from uuid import uuid4

from app.schemas import DeviceCalendar, DeviceEvent, DeviceEventCreateRequest


logger = logging.getLogger(__name__)


class DeviceCalendarService:
    def __init__(self) -> None:
        self._calendars_by_user: dict[str, list[DeviceCalendar]] = {}
        self._events_by_user: dict[str, list[DeviceEvent]] = {}

    def set_calendars(
        self, user_id: str, calendars: list[DeviceCalendar]
    ) -> list[DeviceCalendar]:
        self._calendars_by_user[user_id] = calendars
        return calendars

    def list_calendars(self, user_id: str) -> list[DeviceCalendar]:
        return list(self._calendars_by_user.get(user_id, []))

    def list_events(
        self,
        user_id: str,
        calendar_id: str | None = None,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> list[DeviceEvent]:
        events = list(self._events_by_user.get(user_id, []))
        if calendar_id:
            events = [event for event in events if event.calendar_id == calendar_id]

        if time_min or time_max:
            filtered: list[DeviceEvent] = []
            for event in events:
                if time_min and event.start_date < time_min:
                    continue
                if time_max and event.end_date > time_max:
                    continue
                filtered.append(event)
            events = filtered

        return events

    def create_event(
        self, user_id: str, payload: DeviceEventCreateRequest
    ) -> DeviceEvent:
        event_id = str(uuid4())
        event = DeviceEvent(
            id=event_id,
            calendar_id=payload.calendar_id,
            title=payload.title,
            start_date=payload.start_date,
            end_date=payload.end_date,
            notes=payload.notes,
            location=payload.location,
            all_day=payload.all_day,
            time_zone=payload.time_zone,
            activity_id=payload.activity_id,
            source=payload.source,
            metadata=payload.metadata,
        )
        self._events_by_user.setdefault(user_id, []).append(event)
        return event


_device_calendar_service = DeviceCalendarService()


def get_device_calendar_service() -> DeviceCalendarService:
    return _device_calendar_service
