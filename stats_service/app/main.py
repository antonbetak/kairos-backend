from uuid import UUID
from threading import Thread

import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Header
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db import Base
from app.db import SessionLocal
from app.db import engine
from app.schemas import EstadisticaRespuesta
from app.schemas import LogroRespuesta
from app.schemas import RachaRespuesta
from app.services.estadisticas import obtener_o_crear_estadistica_usuario
from app.services.estadisticas import obtener_o_crear_racha_usuario
from app.services.estadisticas import listar_logros_usuario
from app.services.rabbitmq_consumer import iniciar_consumidor
from app.config import settings

app = FastAPI(title="Kairos Stats Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token inválido o faltante")

    return token


def obtener_id_usuario(authorization: str | None = Header(default=None)):
    token = _extract_bearer_token(authorization)
    try:
        response = httpx.get(
            f"{settings.auth_service_url.rstrip('/')}/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="No fue posible validar la autorización") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    data = response.json()
    user_id = str(data.get("id_usuario") or data.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")

    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


@app.on_event("startup")
def iniciar_base_de_datos():
    Base.metadata.create_all(bind=engine)
    Thread(target=iniciar_consumidor, daemon=True).start()


@app.get("/health")
def health():
    return {"service": "stats_service", "status": "ok"}


@app.get("/estadisticas", response_model=EstadisticaRespuesta)
def obtener_estadisticas(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return obtener_o_crear_estadistica_usuario(db, id_usuario)


@app.get("/rachas/{tipo}", response_model=RachaRespuesta)
def obtener_racha(
    tipo: str,
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return obtener_o_crear_racha_usuario(db, id_usuario, tipo)


@app.get("/logros", response_model=list[LogroRespuesta])
def listar_logros(
    id_usuario: UUID = Depends(obtener_id_usuario),
    db: Session = Depends(get_db),
):
    return listar_logros_usuario(db, id_usuario)
