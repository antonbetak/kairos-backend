import logging
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI

from app.consumers.rabbitmq_consumer import iniciar_consumidor
from app.db.chroma import get_collection
from app.routes.generate import router as generate_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando agent-service...")

    try:
        get_collection()
        logger.info("ChromaDB listo")
    except Exception as e:
        logger.warning("ChromaDB no disponible al inicio: %s", e)

    thread = Thread(target=iniciar_consumidor, daemon=True)
    thread.start()
    logger.info("Consumidor RabbitMQ arrancado en background")

    yield

    logger.info("Cerrando agent-service...")


app = FastAPI(
    title="Kairos Agent Service",
    description="Agente RAG para generación inteligente de horarios",
    lifespan=lifespan,
)

app.include_router(generate_router)


@app.get("/health")
def health():
    return {"service": "agent-service", "status": "ok"}