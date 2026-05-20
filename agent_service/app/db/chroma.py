from __future__ import annotations

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)

_chroma_client: Optional[chromadb.HttpClient] = None
_embeddings: Optional[HuggingFaceEmbeddings] = None
_vectorstore: Optional[Chroma] = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        logger.info("Cargando modelo de embeddings: %s", settings.embedding_model)
        _embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
        logger.info("Embeddings listos")
    return _embeddings


def get_chroma_client() -> chromadb.HttpClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB conectado en %s:%s", settings.chroma_host, settings.chroma_port)
    return _chroma_client


def get_vectorstore() -> Chroma:
    """
    Devuelve el vectorstore de LangChain conectado a ChromaDB HTTP.
    Es el que usamos para similarity_search (RAG).
    """
    global _vectorstore
    if _vectorstore is None:
        client = get_chroma_client()
        _vectorstore = Chroma(
            client=client,
            collection_name=settings.chroma_collection,
            embedding_function=get_embeddings(),
        )
        logger.info("Vectorstore LangChain listo: %s", settings.chroma_collection)
    return _vectorstore


def get_collection():
    """
    Devuelve la colección raw de ChromaDB.
    La usamos para upsert y conteo de documentos.
    """
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_documento(doc_id: str, texto: str, metadata: dict) -> None:
    """Inserta o actualiza un documento en ChromaDB con embeddings."""
    try:
        embeddings = get_embeddings()
        vector = embeddings.embed_query(texto)

        collection = get_collection()
        collection.upsert(
            ids=[doc_id],
            documents=[texto],
            embeddings=[vector],
            metadatas=[metadata],
        )
        logger.info("Upsert ChromaDB: %s", doc_id)
    except Exception as e:
        logger.warning("Error upsert ChromaDB: %s", e)


def buscar_por_tipo(
    id_usuario: str,
    tipo_memoria: str,
    query: str,
    n_results: int = 3,
) -> list[str]:
    """
    Busca documentos de un tipo de memoria específico para un usuario.
    tipo_memoria: 'semantica' | 'episodica' | 'procedimental'
    """
    try:
        vectorstore = get_vectorstore()
        resultados = vectorstore.similarity_search(
            query,
            k=n_results,
            filter={
                "$and": [
                    {"id_usuario": {"$eq": id_usuario}},
                    {"tipo_memoria": {"$eq": tipo_memoria}},
                ]
            },
        )
        docs = [r.page_content for r in resultados]
        logger.info(
            "ChromaDB [%s] query '%s' → %d docs para usuario %s",
            tipo_memoria, query, len(docs), id_usuario,
        )
        return docs
    except Exception as e:
        logger.warning("Error similarity_search ChromaDB: %s", e)
        return []


def contar_documentos_usuario(id_usuario: str) -> int:
    """Cuenta cuántos documentos existen para un usuario."""
    try:
        collection = get_collection()
        resultado = collection.get(where={"id_usuario": id_usuario})
        return len(resultado.get("ids", []))
    except Exception as e:
        logger.warning("Error contando docs usuario: %s", e)
        return 0