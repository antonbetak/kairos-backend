import json
import re
import secrets
from datetime import datetime
from datetime import timezone
from threading import Thread
import unicodedata
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Response
from fastapi import status
from jose import JWTError
from jose import jwt, jwk
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app import models
from app.config import settings
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import TokenResponse
from app.schemas import ClerkUserSync
from app.schemas import ClerkExchangeRequest
from app.schemas import ClerkExchangeResponse
from app.schemas import UserCreate
from app.schemas import UserLogin
from app.schemas import PublicUserResponse
from app.schemas import UserProfileUpdate
from app.schemas import UserResponse
from app.schemas import RefreshTokenRequest
from app.schemas import TokenStatusRequest
from app.schemas import TokenStatusResponse
from app.schemas import TokenBlacklistRequest
from app.schemas import VerifyTokenResponse
from app.schemas import GoogleUserSync
from app.security import create_access_token
from app.security import create_token_session_id
from app.security import create_refresh_token
from app.security import decode_access_token
from app.security import decode_refresh_token
from app.security import get_token_expiration
from app.token_blacklist import blacklist_token
from app.token_blacklist import blacklist_session
from app.token_blacklist import is_token_blacklisted
from app.services.rabbitmq_google_sync import start_google_sync_consumer

app = FastAPI(title="Kairos Auth Service")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
HANDLE_PATTERN = re.compile(r"[^a-z0-9_.]+")
google_sync_thread: Thread | None = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    return token


CLERK_JWKS_CACHE: dict[str, Any] | None = None
CLERK_JWKS_CACHE_AT: datetime | None = None
CLERK_JWKS_CACHE_TTL_SECONDS = 3600


def _slugify_handle(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )
    normalized = normalized.removeprefix("@")
    normalized = HANDLE_PATTERN.sub("_", normalized)
    normalized = re.sub(r"[_\\.]{2,}", "_", normalized).strip("_.")
    return normalized[:60] or "usuario"


def _base_handle_from_user(nombre: str, email: str) -> str:
    email_prefix = str(email).split("@", 1)[0]
    return _slugify_handle(email_prefix or nombre)


def _generate_unique_handle(db: Session, nombre: str, email: str) -> str:
    base = _base_handle_from_user(nombre, email)
    handle = base
    suffix = 2
    while db.execute(select(models.User).where(models.User.handle == handle)).first():
        suffix_text = str(suffix)
        max_base_length = max(1, 60 - len(suffix_text))
        handle = f"{base[:max_base_length]}{suffix_text}"
        suffix += 1
    return handle


def _normalize_requested_handle(value: str) -> str:
    handle = _slugify_handle(value)
    if len(handle) < 3:
        raise HTTPException(
            status_code=400, detail="El handle debe tener al menos 3 caracteres"
        )
    return handle


def _fetch_clerk_jwks() -> dict[str, Any] | None:
    global CLERK_JWKS_CACHE, CLERK_JWKS_CACHE_AT
    if not settings.clerk_jwks_url:
        return None

    now = datetime.now(timezone.utc)
    if (
        CLERK_JWKS_CACHE is not None
        and CLERK_JWKS_CACHE_AT is not None
        and (now - CLERK_JWKS_CACHE_AT).total_seconds() < CLERK_JWKS_CACHE_TTL_SECONDS
    ):
        return CLERK_JWKS_CACHE

    try:
        with urlopen(settings.clerk_jwks_url, timeout=10) as response:
            raw = response.read()
            jwks = json.loads(raw)
    except (URLError, ValueError, OSError):
        return CLERK_JWKS_CACHE

    if not isinstance(jwks, dict) or "keys" not in jwks:
        return CLERK_JWKS_CACHE

    CLERK_JWKS_CACHE = jwks
    CLERK_JWKS_CACHE_AT = now
    return jwks


def _verify_clerk_jwt(token: str) -> dict[str, Any]:
    jwks = _fetch_clerk_jwks()
    if not jwks:
        raise HTTPException(
            status_code=500,
            detail="Clerk JWKS no está disponible; revisa CLERK_JWKS_URL",
        )

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Clerk token inválido")

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Clerk token inválido")

    key_data = next(
        (key for key in jwks.get("keys", []) if key.get("kid") == kid),
        None,
    )
    if not key_data:
        raise HTTPException(status_code=401, detail="Clerk token inválido")

    algorithm = key_data.get("alg", "RS256")
    try:
        public_key = jwk.construct(key_data)
        return jwt.decode(
            token,
            public_key,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Clerk token expirado")
    except JWTError:
        raise HTTPException(status_code=401, detail="Clerk token inválido")


def _profile_from_clerk_claims(payload: dict[str, Any]) -> dict[str, str | None]:
    clerk_user_id = str(payload.get("sub") or payload.get("user_id") or "").strip()
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="Clerk token inválido")

    email = (
        str(
            payload.get("email")
            or payload.get("primary_email_address")
            or payload.get("email_address")
            or ""
        )
        .strip()
        .lower()
    )

    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    nombre = " ".join(part for part in (first_name, last_name) if part).strip()
    if not nombre:
        nombre = str(payload.get("full_name") or payload.get("name") or "").strip()
    nombre = nombre or (email.split("@", 1)[0] if email else "")

    return {
        "clerk_id": clerk_user_id,
        "email": email or None,
        "nombre": nombre or None,
    }


def _find_or_create_user_by_email(
    profile: dict[str, str | None], db: Session
) -> models.User:
    # Prefer lookup by clerk_id when available
    clerk_id = profile.get("clerk_id")
    if clerk_id:
        user = db.execute(
            select(models.User).where(models.User.clerk_id == clerk_id)
        ).scalar_one_or_none()
        if user:
            # ensure handle and other fields are present
            updated = False
            if not user.handle:
                user.handle = _generate_unique_handle(db, user.nombre, user.email)
                updated = True
            if updated:
                db.commit()
                db.refresh(user)
            return user

    # Fall back to email lookup/creation
    email = profile.get("email")
    user = db.execute(
        select(models.User).where(models.User.email == email)
    ).scalar_one_or_none()

    if user:
        updated = False
        if clerk_id and not user.clerk_id:
            user.clerk_id = clerk_id
            updated = True
        if not user.handle:
            user.handle = _generate_unique_handle(db, user.nombre, user.email)
            updated = True
        if updated:
            db.commit()
            db.refresh(user)
        return user

    # Create new user when none found
    nombre = str(profile.get("nombre") or (email or "").split("@", 1)[0]).strip()
    user = models.User(
        nombre=nombre or "Usuario Kairos",
        email=email,
        clerk_id=clerk_id,
        handle=_generate_unique_handle(db, nombre, email),
        password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear usuario Clerk")
    db.refresh(user)
    return user


def _get_user_from_authorization(
    authorization: str | None,
    db: Session,
) -> models.User:
    token = _extract_bearer_token(authorization)

    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token invalidado")

    try:
        payload = decode_access_token(token)
        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise HTTPException(status_code=401, detail="token invalido")
    except ExpiredSignatureError:
        blacklist_token(token, get_token_expiration(token))
        raise HTTPException(status_code=401, detail="Token expirado")
    except JWTError:
        raise HTTPException(status_code=401, detail="token invalido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="token invalido")

    try:
        user_uuid = UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="token invalido")

    user = db.execute(
        select(models.User).where(models.User.id_usuario == user_uuid)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return user


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS usuarios ADD COLUMN IF NOT EXISTS clerk_id VARCHAR(120)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS usuarios ADD COLUMN IF NOT EXISTS handle VARCHAR(60)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS usuarios ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_clerk_id ON usuarios (clerk_id)"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_handle ON usuarios (handle)"
        )

    global google_sync_thread
    if google_sync_thread is None or not google_sync_thread.is_alive():
        google_sync_thread = Thread(target=start_google_sync_consumer, daemon=True)
        google_sync_thread.start()


@app.get("/health")
def health():
    return {"service": "auth_service", "status": "ok"}


@app.post("/auth/register", response_model=UserResponse)
def register_user(
    user_data: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    existing_user = db.execute(
        select(models.User).where(models.User.email == user_data.email)
    ).scalar_one_or_none()

    if existing_user:
        response.status_code = status.HTTP_200_OK
        return existing_user

    user = models.User(
        nombre=user_data.nombre,
        email=user_data.email,
        handle=_generate_unique_handle(db, user_data.nombre, user_data.email),
        password_hash=pwd_context.hash(user_data.password),
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")

    db.refresh(user)
    response.status_code = status.HTTP_201_CREATED
    return user


def _verify_internal_token(x_internal_token: str | None) -> None:
    if (
        settings.internal_service_token
        and x_internal_token != settings.internal_service_token
    ):
        raise HTTPException(status_code=403, detail="Token interno invalido")


@app.post("/auth/clerk/sync", response_model=UserResponse)
def sync_clerk_user(
    payload: ClerkUserSync,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    db: Session = Depends(get_db),
):
    _verify_internal_token(x_internal_token)

    user = db.execute(
        select(models.User).where(models.User.clerk_id == payload.clerk_id)
    ).scalar_one_or_none()
    if user:
        if payload.avatar_url and user.avatar_url != payload.avatar_url:
            user.avatar_url = payload.avatar_url
            db.commit()
            db.refresh(user)
        return user

    user = db.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()
    if user:
        user.clerk_id = payload.clerk_id
        if payload.avatar_url and not user.avatar_url:
            user.avatar_url = payload.avatar_url
        if not user.handle:
            user.handle = _generate_unique_handle(db, user.nombre, user.email)
        db.commit()
        db.refresh(user)
        return user

    nombre = (payload.nombre or payload.email.split("@", 1)[0]).strip()
    user = models.User(
        nombre=nombre or "Usuario Kairos",
        email=payload.email,
        clerk_id=payload.clerk_id,
        handle=_generate_unique_handle(db, nombre, payload.email),
        avatar_url=payload.avatar_url,
        password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Usuario Clerk ya registrado")

    db.refresh(user)
    return user


@app.post("/auth/internal/google/sync", response_model=TokenResponse)
def sync_google_user_and_issue_tokens(
    payload: GoogleUserSync,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    db: Session = Depends(get_db),
):
    _verify_internal_token(x_internal_token)

    user = db.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()

    if user:
        updates = False
        if payload.picture and user.avatar_url != payload.picture:
            user.avatar_url = payload.picture
            updates = True
        if not user.handle:
            user.handle = _generate_unique_handle(db, user.nombre, user.email)
            updates = True
        if updates:
            db.commit()
            db.refresh(user)
    else:
        user = models.User(
            nombre=payload.nombre.strip() or payload.email.split("@", 1)[0],
            email=payload.email,
            handle=_generate_unique_handle(db, payload.nombre, payload.email),
            avatar_url=payload.picture,
            password_hash=pwd_context.hash(secrets.token_urlsafe(32)),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Email already registered")
        db.refresh(user)

    session_id = create_token_session_id()
    access_token, expires_in = create_access_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=session_id,
    )
    refresh_token, refresh_expires_in = create_refresh_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=session_id,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
    )


@app.post("/auth/login", response_model=TokenResponse)
def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    email = login_data.email.strip().lower()
    user = db.execute(
        select(models.User).where(models.User.email == email)
    ).scalar_one_or_none()

    if not user or not pwd_context.verify(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_id = create_token_session_id()

    access_token, expires_in = create_access_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=session_id,
    )

    refresh_token, refresh_expires_in = create_refresh_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=session_id,
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
    )


@app.post("/auth/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    refresh_token_value = payload.refresh_token.strip()
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    if is_token_blacklisted(refresh_token_value):
        raise HTTPException(status_code=401, detail="Token invalidado")

    try:
        claims = decode_refresh_token(refresh_token_value)
    except ExpiredSignatureError:
        blacklist_token(refresh_token_value, get_token_expiration(refresh_token_value))
        raise HTTPException(status_code=401, detail="Token expirado")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido")

    user_id = claims.get("sub")
    email = claims.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Token invalido")

    try:
        user_uuid = UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="Token invalido")

    user = db.execute(
        select(models.User).where(models.User.id_usuario == user_uuid)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    session_id = str(claims.get("sid") or "").strip()
    if session_id:
        blacklist_session(session_id, get_token_expiration(refresh_token_value))

    blacklist_token(refresh_token_value, get_token_expiration(refresh_token_value))

    new_session_id = create_token_session_id()
    new_access_token, access_expires_in = create_access_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=new_session_id,
    )
    new_refresh_token, refresh_expires_in = create_refresh_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=new_session_id,
    )

    return TokenResponse(
        access_token=new_access_token,
        expires_in=access_expires_in,
        refresh_token=new_refresh_token,
        refresh_expires_in=refresh_expires_in,
    )


@app.get("/auth/me", response_model=UserResponse)
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    return _get_user_from_authorization(authorization, db)


@app.patch("/auth/me/profile", response_model=UserResponse)
def update_profile(
    payload: UserProfileUpdate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    user = _get_user_from_authorization(authorization, db)

    if payload.nombre is not None:
        user.nombre = payload.nombre.strip()

    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url.strip() or None

    if payload.handle is not None:
        handle = _normalize_requested_handle(payload.handle)
        existing = db.execute(
            select(models.User).where(models.User.handle == handle)
        ).scalar_one_or_none()
        if existing and existing.id_usuario != user.id_usuario:
            raise HTTPException(status_code=409, detail="Handle no disponible")
        user.handle = handle

    db.commit()
    db.refresh(user)
    return user


@app.get("/auth/users/search", response_model=list[PublicUserResponse])
def search_users(
    handle: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    query = _slugify_handle(handle)
    if not query:
        return []

    limit = min(max(limit, 1), 25)
    return (
        db.execute(
            select(models.User)
            .where(models.User.handle.ilike(f"{query}%"))
            .order_by(models.User.handle.asc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


@app.get("/auth/users/{id_usuario}/public", response_model=PublicUserResponse)
def public_profile(id_usuario: UUID, db: Session = Depends(get_db)):
    user = db.execute(
        select(models.User).where(models.User.id_usuario == id_usuario)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


@app.get("/auth/verify", response_model=VerifyTokenResponse)
def verify_token(authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)

    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token invalidado")

    try:
        payload = decode_access_token(token)
        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise HTTPException(status_code=401, detail="token invalido")
        user_id = payload.get("sub")
        email = payload.get("email")
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="token invalido")
    except ExpiredSignatureError:
        blacklist_token(token, get_token_expiration(token))
        raise HTTPException(status_code=401, detail="token expirado")
    except JWTError:
        raise HTTPException(status_code=401, detail="token invalido")

    return VerifyTokenResponse(valid=True, id_usuario=user_id, email=email)


@app.post("/auth/clerk/exchange", response_model=ClerkExchangeResponse)
def clerk_exchange(
    payload: ClerkExchangeRequest,
    db: Session = Depends(get_db),
):
    claims = _verify_clerk_jwt(payload.clerk_token)
    clerk_id = str(claims.get("sub") or claims.get("user_id") or "").strip()
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Clerk token inválido")

    user = db.execute(
        select(models.User).where(models.User.clerk_id == clerk_id)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario Clerk no registrado")

    session_id = create_token_session_id()
    access_token, expires_in = create_access_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=session_id,
    )
    refresh_token, refresh_expires_in = create_refresh_token(
        user_id=user.id_usuario,
        email=user.email,
        session_id=session_id,
    )

    return ClerkExchangeResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
        user=user,
    )


@app.post("/auth/token-status", response_model=TokenStatusResponse)
def token_status(payload: TokenStatusRequest):
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    return TokenStatusResponse(blacklisted=is_token_blacklisted(token))


@app.post("/auth/token-blacklist", response_model=TokenStatusResponse)
def token_blacklist(payload: TokenBlacklistRequest):
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    blacklist_token(token, get_token_expiration(token))
    return TokenStatusResponse(blacklisted=True)
