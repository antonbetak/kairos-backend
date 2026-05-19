from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ActivityEventCreate(BaseModel):
    event_type: str
    title: str
    message: str
    visibility: str = Field(default="friends", pattern="^(private|friends|public)$")
    source_entity_id: str | None = None
    extra_data: dict | None = None


class ActivityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_evento: UUID
    actor_id: UUID
    event_type: str
    title: str
    message: str
    source_service: str | None
    source_event_id: str | None
    source_entity_id: str | None
    visibility: str
    extra_data: dict | None
    created_at: datetime


class VisibilityUpdate(BaseModel):
    visibility: str = Field(pattern="^(private|friends|public)$")


class FriendRequestCreate(BaseModel):
    addressee_id: UUID


class FriendshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requester_id: UUID
    addressee_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class InviteCreate(BaseModel):
    max_uses: int = Field(default=1, ge=1, le=25)
    expires_at: datetime | None = None


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    code: str
    max_uses: int
    used_count: int
    expires_at: datetime | None
    created_at: datetime


class ReactionCreate(BaseModel):
    reaction: str = Field(min_length=1, max_length=40)


class ReactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    actor_id: UUID
    reaction: str
    created_at: datetime


class CommentCreate(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    actor_id: UUID
    message: str
    created_at: datetime
