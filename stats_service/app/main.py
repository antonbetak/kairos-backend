from fastapi import FastAPI

from app.db import Base
from app.db import engine

app = FastAPI(title="Kairos Stats Service")


@app.on_event("startup")
def iniciar_base_de_datos():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"service": "stats_service", "status": "ok"}
