from pydantic import BaseModel, EmailStr


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


class GoogleAuthResponse(BaseModel):
    provider: str = "google"
    user: GoogleUserProfile
    tokens: GoogleTokenSet


class GoogleRefreshRequest(BaseModel):
    refresh_token: str


class GoogleRefreshResponse(BaseModel):
    provider: str = "google"
    tokens: GoogleTokenSet


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
