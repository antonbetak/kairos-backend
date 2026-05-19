from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


class UserCreate(BaseModel):
    nombre: str
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ClerkUserSync(BaseModel):
    clerk_id: str
    email: str
    nombre: str | None = None
    avatar_url: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: UUID
    nombre: str
    email: str
    clerk_id: str | None = None
    handle: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PublicUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: UUID
    nombre: str
    handle: str | None = None
    avatar_url: str | None = None


class UserProfileUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    handle: str | None = Field(
        default=None,
        min_length=3,
        max_length=60,
        pattern="^@?[a-z0-9_\\.]+$",
    )
    avatar_url: str | None = Field(default=None, max_length=500)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    refresh_expires_in: int | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenStatusRequest(BaseModel):
    token: str


class TokenStatusResponse(BaseModel):
    blacklisted: bool


class TokenBlacklistRequest(BaseModel):
    token: str


class VerifyTokenResponse(BaseModel):
    valid: bool
    id_usuario: UUID
    email: str


class GoogleUserSync(BaseModel):
    email: str
    nombre: str
    picture: str | None = None
    google_id: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()
