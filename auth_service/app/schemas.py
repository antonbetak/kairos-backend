from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator


class UserCreate(BaseModel):
    nombre: str
    email: str
    password: str

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
    created_at: datetime
    updated_at: datetime


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
