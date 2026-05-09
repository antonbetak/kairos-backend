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
from app.schemas import UserCreate
from app.schemas import UserResponse

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
