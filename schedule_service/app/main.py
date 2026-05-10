from fastapi import FastAPI
from app import models
from app.database import Base
from app.database import engine

app = FastAPI(title="Kairos Schedule Service")


@app.on_event("startup")
def crear_tablas():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"service": "schedule-service", "status": "ok"}
