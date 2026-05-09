from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import UUID

from jose import jwt

from app.config import settings


def create_access_token(user_id: UUID, email: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    expires_at = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
