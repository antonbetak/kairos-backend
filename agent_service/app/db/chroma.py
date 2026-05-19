import logging
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)

_client: chromadb.HttpClient | None = None
_collection = None


def get_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB conectado en %s:%s", settings.chroma_host, settings.chroma_port)
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Colección ChromaDB lista: %s", settings.chroma_collection)
    return _collection


def upsert_documento(doc_id: str, texto: str, metadata: dict) -> None:
    """Inserta o actualiza un documento de patrones de usuario en ChromaDB."""
    try:
        collection = get_collection()
        collection.upsert(
            ids=[doc_id],
            documents=[texto],
            metadatas=[metadata],
        )
        logger.info("Documento upserted en ChromaDB: %s", doc_id)
    except Exception as e:
        logger.warning("Error al hacer upsert en ChromaDB: %s", e)


def query_patrones(id_usuario: str, query_texto: str, n_results: int = 3) -> list[str]:
    """Recupera documentos relevantes de un usuario dado un query de texto."""
    try:
        collection = get_collection()
        resultados = collection.query(
            query_texts=[query_texto],
            n_results=n_results,
            where={"id_usuario": id_usuario},
        )
        documentos = resultados.get("documents", [[]])[0]
        logger.info(
            "ChromaDB query '%s' → %d docs para usuario %s",
            query_texto, len(documentos), id_usuario,
        )
        return documentos
    except Exception as e:
        logger.warning("Error al query ChromaDB: %s", e)
        return []


def contar_documentos_usuario(id_usuario: str) -> int:
    """Cuenta cuántos documentos existen para un usuario (para detectar usuario nuevo)."""
    try:
        collection = get_collection()
        resultados = collection.get(where={"id_usuario": id_usuario})
        return len(resultados.get("ids", []))
    except Exception as e:
        logger.warning("Error al contar documentos de usuario: %s", e)
        return 0