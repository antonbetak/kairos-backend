from pydantic import BaseModel, EmailStr, Field
from pydantic import ConfigDict


class GoogleUserProfile(BaseModel):
    email: EmailStr
    name: str
    picture: str | None = None
    google_id: str
    email_verified: bool = False


class GoogleTokenSet(BaseModel):
    access_token: str
    token_type: str
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None
    id_token: str | None = None


class KairosUserProfile(BaseModel):
    id_usuario: str
    nombre: str
    email: EmailStr
    handle: str | None = None
    avatar_url: str | None = None


class KairosTokenSet(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class GoogleAuthResponse(BaseModel):
    provider: str = "google"
    user: GoogleUserProfile
    tokens: GoogleTokenSet
    kairos_user: KairosUserProfile
    kairos_tokens: KairosTokenSet


class GoogleAuthUrlResponse(BaseModel):
    url: str


class GoogleMeResponse(BaseModel):
    provider: str = "google"
    user: GoogleUserProfile


class GoogleRefreshRequest(BaseModel):
    refresh_token: str
    access_token: str | None = None
    platform: str | None = None


class GoogleRefreshResponse(BaseModel):
    provider: str = "google"
    tokens: GoogleTokenSet


class GoogleClerkSessionRequest(BaseModel):
    user: GoogleUserProfile
    tokens: GoogleTokenSet
    provider: str = "google"


class GoogleTokenSaveRequest(BaseModel):
    access_token: str = Field(..., alias="google_access_token")
    refresh_token: str | None = Field(default=None, alias="google_refresh_token")
    id_token: str | None = Field(default=None, alias="google_id_token")

    model_config = ConfigDict(populate_by_name=True)


class GoogleTokenSaveResponse(BaseModel):
    success: bool
    message: str
    calendar_valid: bool
    fit_valid: bool
    calendar_error: str | None = None
    fit_error: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
