from fastapi import FastAPI
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import TokenResponse
from app.schemas import UserCreate
from app.schemas import UserLogin
from app.schemas import UserResponse
from app.security import create_access_token

app = FastAPI(title="Kairos Auth Service")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"service": "auth_service", "status": "ok"}


@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.execute(
        select(models.User).where(models.User.email == user_data.email)
    ).scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

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
    return user


@app.post("/auth/login", response_model=TokenResponse)
def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    email = login_data.email.strip().lower()
    user = db.execute(
        select(models.User).where(models.User.email == email)
    ).scalar_one_or_none()

    if not user or not pwd_context.verify(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token, expires_in = create_access_token(
        user_id=user.id_usuario,
        email=user.email,
    )

    return TokenResponse(access_token=access_token, expires_in=expires_in)
