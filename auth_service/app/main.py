from fastapi import FastAPI

from app.database import Base
from app.database import engine
from app import models

app = FastAPI(title="Kairos Auth Service")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"service": "auth_service", "status": "ok"}
