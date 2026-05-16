from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
	model_config = ConfigDict(extra="allow", populate_by_name=True)


class HealthResponse(BaseModel):
	status: str
	service: str
	environment: str


class ReadyResponse(BaseModel):
	status: str
	service: str


class GoogleTokenSet(BaseSchema):
	access_token: str
	token_type: str
	expires_in: int | None = None
	refresh_token: str | None = None
	scope: str | None = None
	id_token: str | None = None


class GoogleRefreshRequest(BaseModel):
	refresh_token: str
	access_token: str | None = None


class GoogleRefreshResponse(BaseModel):
	provider: str = "google"
	tokens: GoogleTokenSet


class CalendarListItem(BaseSchema):
	id: str
	summary: str | None = None
	description: str | None = None
	time_zone: str | None = Field(None, alias="timeZone")
	access_role: str | None = Field(None, alias="accessRole")
	primary: bool | None = None


class CalendarListResponse(BaseSchema):
	items: list[CalendarListItem] = []
	next_page_token: str | None = Field(None, alias="nextPageToken")
	next_sync_token: str | None = Field(None, alias="nextSyncToken")


class EventReminder(BaseSchema):
	method: str | None = None
	minutes: int | None = None


class EventReminders(BaseSchema):
	use_default: bool | None = Field(None, alias="useDefault")
	overrides: list[EventReminder] | None = None


class EventAttendee(BaseSchema):
	email: str
	display_name: str | None = Field(None, alias="displayName")
	response_status: str | None = Field(None, alias="responseStatus")


class EventDateTime(BaseSchema):
	date: str | None = None
	date_time: str | None = Field(None, alias="dateTime")
	time_zone: str | None = Field(None, alias="timeZone")


class EventItem(BaseSchema):
	id: str | None = None
	status: str | None = None
	summary: str | None = None
	description: str | None = None
	location: str | None = None
	html_link: str | None = Field(None, alias="htmlLink")
	start: EventDateTime | None = None
	end: EventDateTime | None = None
	created: str | None = None
	updated: str | None = None
	organizer: dict[str, Any] | None = None
	creator: dict[str, Any] | None = None
	attendees: list[EventAttendee] | None = None
	reminders: EventReminders | None = None


class EventsListResponse(BaseSchema):
	items: list[EventItem] = []
	next_page_token: str | None = Field(None, alias="nextPageToken")
	next_sync_token: str | None = Field(None, alias="nextSyncToken")


class EventDateTimeInput(BaseModel):
	date: str | None = None
	date_time: str | None = Field(None, alias="dateTime")
	time_zone: str | None = Field(None, alias="timeZone")

	model_config = ConfigDict(populate_by_name=True)


class EventReminderInput(BaseModel):
	method: str
	minutes: int


class EventAttendeeInput(BaseModel):
	email: str
	display_name: str | None = Field(None, alias="displayName")

	model_config = ConfigDict(populate_by_name=True)


class CreateEventRequest(BaseModel):
	calendar_id: str | None = "primary"
	summary: str
	description: str | None = None
	location: str | None = None
	start: EventDateTimeInput
	end: EventDateTimeInput
	attendees: list[EventAttendeeInput] | None = None
	reminders: list[EventReminderInput] | None = None
	send_updates: str | None = Field(None, description="all|externalOnly|none")


class UpdateEventRequest(BaseModel):
	calendar_id: str | None = "primary"
	summary: str | None = None
	description: str | None = None
	location: str | None = None
	start: EventDateTimeInput | None = None
	end: EventDateTimeInput | None = None
	attendees: list[EventAttendeeInput] | None = None
	reminders: list[EventReminderInput] | None = None
	send_updates: str | None = Field(None, description="all|externalOnly|none")


class DeleteResponse(BaseModel):
	status: str
	deleted: bool


class DeviceCalendar(BaseModel):
	id: str
	title: str
	source: str | None = None
	color: str | None = None
	is_primary: bool | None = None
	allows_modifications: bool | None = None


class DeviceCalendarsResponse(BaseModel):
	items: list[DeviceCalendar] = []


class DeviceCalendarsSyncRequest(BaseModel):
	calendars: list[DeviceCalendar]


class DeviceEvent(BaseModel):
	id: str | None = None
	calendar_id: str
	title: str
	start_date: str
	end_date: str
	notes: str | None = None
	location: str | None = None
	all_day: bool | None = None
	time_zone: str | None = None
	activity_id: str | None = None
	source: str | None = None
	metadata: dict[str, object] | None = None


class DeviceEventsResponse(BaseModel):
	items: list[DeviceEvent] = []


class DeviceEventCreateRequest(BaseModel):
	calendar_id: str
	title: str
	start_date: str
	end_date: str
	notes: str | None = None
	location: str | None = None
	all_day: bool | None = None
	time_zone: str | None = None
	activity_id: str | None = None
	source: str | None = None
	metadata: dict[str, object] | None = None


class DeviceEventCreateResponse(BaseModel):
	event: DeviceEvent
