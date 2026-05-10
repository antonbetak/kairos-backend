from fastapi import FastAPI

from app import models
from app.database import Base
from app.database import engine

app = FastAPI(title="Kairos Task Service")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"service": "task_service", "status": "ok"}
