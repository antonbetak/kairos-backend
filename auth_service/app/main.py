from fastapi import FastAPI
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Response
from fastapi import status
from jose import JWTError
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid import UUID

from app import models
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import TokenResponse
from app.schemas import UserCreate
from app.schemas import UserLogin
from app.schemas import UserResponse
from app.schemas import RefreshTokenRequest
from app.schemas import TokenStatusRequest
from app.schemas import TokenStatusResponse
from app.schemas import TokenBlacklistRequest
from app.schemas import VerifyTokenResponse
from app.security import create_access_token
from app.security import create_token_session_id
from app.security import create_refresh_token
from app.security import decode_access_token
from app.security import decode_refresh_token
from app.security import get_token_expiration
from app.token_blacklist import blacklist_token
from app.token_blacklist import blacklist_session
from app.token_blacklist import is_token_blacklisted

app = FastAPI(title="Kairos Auth Service")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS usuarios ADD COLUMN IF NOT EXISTS handle VARCHAR(60)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE IF EXISTS usuarios ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)"
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_handle ON usuarios (handle)"
        )


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
