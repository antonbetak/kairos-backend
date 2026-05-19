import json
import logging
from datetime import datetime

from google import genai

from app.config import settings
from app.db.chroma import contar_documentos_usuario, query_patrones
from app.schemas import BloqueAgente, GenerateRequest, GenerateResponse
from app.services.fallback import generar_horario_fallback

logger = logging.getLogger(__name__)

# Mínimo de documentos en ChromaDB para considerar que hay historial suficiente
MIN_DOCS_PARA_RAG = 3

_client_gemini = genai.Client(api_key=settings.gemini_api_key)


def _construir_contexto_rag(id_usuario: str) -> str:
    """
    Lanza tres queries en paralelo a ChromaDB y concatena los resultados
    como contexto para el prompt de Gemini.
    """
    queries = [
        ("patrones de productividad y horas más activas del usuario", "productividad"),
        ("hábitos que el usuario abandona o le cuestan mantener", "habitos en riesgo"),
        ("carga máxima de tareas que el usuario completa en un día", "carga diaria"),
    ]

    secciones = []
    for query_texto, etiqueta in queries:
        docs = query_patrones(id_usuario, query_texto, n_results=3)
        if docs:
            contenido = "\n- ".join(docs)
            secciones.append(f"### {etiqueta.upper()}\n- {contenido}")

    if not secciones:
        return ""

    return "\n\n".join(secciones)


def _construir_prompt(request: GenerateRequest, contexto_rag: str) -> str:
    fecha_str = request.fecha.strftime("%A %d de %B de %Y")

    tareas_str = "\n".join(
        f"- [{t.tipo or 'tarea'}] {t.titulo}"
        f"{f' (límite: {t.fecha_limite.date()})' if t.fecha_limite else ''}"
        f"{f' (~{t.duracion_estimada_min} min)' if t.duracion_estimada_min else ''}"
        for t in request.tareas
    ) or "Sin tareas pendientes."

    metas_str = "\n".join(
        f"- {m.titulo} ({m.progreso_pct:.0f}% completada)"
        for m in request.metas
    ) or "Sin metas activas."

    streaks_str = "\n".join(
        f"- {s.tipo_habito}: racha actual {s.racha_actual} días"
        f" (máx {s.racha_maxima})"
        for s in request.streaks
    ) or "Sin streaks activos."

    return f"""Eres un asistente de productividad personal para la app Kairos.
Tu tarea es generar un horario diario óptimo para el usuario basado en su contexto actual y su historial de comportamiento.

## FECHA
{fecha_str}

## CONTEXTO DEL USUARIO (historial de comportamiento)
{contexto_rag if contexto_rag else "Usuario nuevo, sin historial suficiente aún."}

## TAREAS PENDIENTES
{tareas_str}

## METAS ACTIVAS
{metas_str}

## STREAKS / HÁBITOS
{streaks_str}

## INSTRUCCIONES
- Genera entre 3 y 6 bloques de tiempo para el día.
- Prioriza las tareas con deadline más cercano.
- Incluye al menos un hábito si hay streaks activos, especialmente los de racha > 3 días (no romper la racha).
- Usa el historial de comportamiento para decidir en qué horas poner cada tipo de actividad.
- Los tipos válidos son: "tarea", "habito", "evento", "libre".
- No programes nada antes de las 06:00 ni después de las 22:00.
- Cada bloque debe durar al menos 15 minutos.
- Incluye un campo "razon" breve explicando por qué propones ese bloque en ese horario.

## FORMATO DE RESPUESTA
Responde ÚNICAMENTE con un JSON válido, sin texto extra, sin bloques de código markdown.
El JSON debe tener esta estructura exacta:
{{
  "bloques": [
    {{
      "titulo": "nombre del bloque",
      "descripcion": "descripción opcional o null",
      "fecha_inicio": "YYYY-MM-DDTHH:MM:00",
      "fecha_fin": "YYYY-MM-DDTHH:MM:00",
      "tipo": "tarea|habito|evento|libre",
      "razon": "por qué se propone este bloque en este horario"
    }}
  ]
}}
"""


def _parsear_respuesta_gemini(texto: str, request: GenerateRequest) -> list[BloqueAgente]:
    """Parsea el JSON que devuelve Gemini y lo convierte en BloqueAgente."""
    # Limpiar posibles bloques de código que Gemini a veces agrega
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    data = json.loads(texto)
    bloques = []

    for item in data.get("bloques", []):
        bloques.append(BloqueAgente(
            titulo=item["titulo"],
            descripcion=item.get("descripcion"),
            fecha_inicio=datetime.fromisoformat(item["fecha_inicio"]),
            fecha_fin=datetime.fromisoformat(item["fecha_fin"]),
            tipo=item["tipo"],
            razon=item.get("razon"),
        ))

    return bloques


async def generar_horario(request: GenerateRequest) -> GenerateResponse:
    """
    Punto de entrada principal del agente.
    1. Revisa si hay suficiente historial en ChromaDB
    2. Si no → fallback con heurísticas
    3. Si sí → RAG + Gemini
    """
    id_usuario = request.id_usuario
    n_docs = contar_documentos_usuario(id_usuario)

    if n_docs < MIN_DOCS_PARA_RAG:
        logger.info(
            "Usuario %s tiene solo %d docs en ChromaDB, usando fallback",
            id_usuario, n_docs,
        )
        return generar_horario_fallback(request)

    # Construir contexto RAG
    contexto_rag = _construir_contexto_rag(id_usuario)

    # Construir prompt
    prompt = _construir_prompt(request, contexto_rag)

    try:
        logger.info("Llamando a Gemini para usuario %s, fecha %s", id_usuario, request.fecha)
        response = _client_gemini.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
        texto_respuesta = response.text

        bloques = _parsear_respuesta_gemini(texto_respuesta, request)

        return GenerateResponse(
            id_usuario=id_usuario,
            fecha=request.fecha,
            bloques=bloques,
            es_fallback=False,
        )

    except json.JSONDecodeError as e:
        logger.warning("Gemini devolvió JSON inválido: %s — usando fallback", e)
        return generar_horario_fallback(request)

    except Exception as e:
        logger.warning("Error en llamada a Gemini: %s — usando fallback", e)
        return generar_horario_fallback(request)