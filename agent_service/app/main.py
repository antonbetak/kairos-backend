from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from threading import Thread

import os
from app.config import settings

from fastapi import FastAPI

from app.consumers.rabbitmq_consumer import iniciar_consumidor
from app.db.chroma import get_collection, get_embeddings
from app.routes.generate import router as generate_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando agent-service...")

    # Precalentar embeddings
    try:
        get_embeddings()
        logger.info("Embeddings listos")
    except Exception as e:
        logger.warning("Error cargando embeddings: %s", e)

    # Verificar ChromaDB
    try:
        get_collection()
        logger.info("ChromaDB listo")
    except Exception as e:
        logger.warning("ChromaDB no disponible al inicio: %s", e)

    # Arrancar consumer RabbitMQ en background
    thread = Thread(target=iniciar_consumidor, daemon=True)
    thread.start()
    logger.info("Consumidor RabbitMQ arrancado en background")

    yield

    logger.info("Cerrando agent-service...")

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

app = FastAPI(
    title="Kairos Agent Service",
    description="Agente RAG con LangGraph, Gemini y ChromaDB",
    lifespan=lifespan,
)

app.include_router(generate_router)


@app.get("/health")
def health():
    return {"service": "agent-service", "status": "ok"}
