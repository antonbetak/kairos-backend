from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Literal

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import MessagesState
from langgraph.store.base import BaseStore
from trustcall import create_extractor

from app.agent.prompts import (
    INSTRUCCION_ACTUALIZAR_MEMORIA,
    INSTRUCCION_PROCEDIMENTAL,
    PROMPT_SISTEMA,
)
from app.agent.tools import ActualizarMemoria, generar_horario_dia
from app.config import settings
from app.db.chroma import buscar_por_tipo, upsert_documento

logger = logging.getLogger(__name__)

modelo = ChatGoogleGenerativeAI(
    model=settings.gemini_model,
    google_api_key=settings.gemini_api_key,
)

tools_list = [generar_horario_dia]
todas_las_tools = [ActualizarMemoria] + tools_list

# Extractores Trustcall para cada tipo de memoria
extractor_semantica = create_extractor(
    modelo,
    tools=[ActualizarMemoria],
    tool_choice="ActualizarMemoria",
)
extractor_procedimental = create_extractor(
    modelo,
    tools=[ActualizarMemoria],
    tool_choice="ActualizarMemoria",
)

def _cargar_memoria(store: BaseStore, id_usuario: str, tipo: str) -> str:
    """Carga memorias del InMemoryStore de LangGraph."""
    mems = store.search((tipo, id_usuario))
    if not mems:
        return f"Sin {tipo} registrada aún."
    return "\n".join(str(m.value) for m in mems)


def _enriquecer_desde_chroma(id_usuario: str, tipo: str, query: str) -> str:
    """
    Complementa la memoria del store con búsqueda semántica en ChromaDB.
    ChromaDB tiene el historial persistente entre reinicios.
    """
    docs = buscar_por_tipo(id_usuario, tipo, query, n_results=3)
    if not docs:
        return ""
    return "\n".join(docs)


def _formatear_tarea(t: dict) -> str:
    linea = f"- [{t.get('tipo', 'tarea')}] {t.get('titulo', '')}"
    if t.get('fecha_limite'):
        linea += f" (límite: {t.get('fecha_limite')})"
    if t.get('duracion_estimada_min'):
        linea += f" (~{t.get('duracion_estimada_min')} min)"
    return linea


def _formatear_contexto(request_data: dict) -> dict:
    tareas = request_data.get("tareas", [])
    metas = request_data.get("metas", [])
    streaks = request_data.get("streaks", [])
    eventos = request_data.get("eventos_calendario", [])
    fecha = request_data.get("fecha", "hoy")

    tareas_str = "\n".join(_formatear_tarea(t) for t in tareas) or "Sin tareas pendientes."

    metas_str = "\n".join(
        f"- {m.get('titulo')} ({m.get('progreso_pct', 0):.0f}% completada)"
        for m in metas
    ) or "Sin metas activas."

    streaks_str = "\n".join(
        f"- {s.get('tipo_habito')}: racha actual {s.get('racha_actual')} días (máx {s.get('racha_maxima')})"
        for s in streaks
    ) or "Sin streaks activos."

    eventos_str = "\n".join(
        f"- {e.get('titulo')} de {e.get('inicio')} a {e.get('fin')}"
        for e in eventos
    ) or "Sin eventos en Google Calendar para hoy."

    return {
        "fecha": str(fecha),
        "tareas": tareas_str,
        "metas": metas_str,
        "streaks": streaks_str,
        "eventos_calendario": eventos_str,
    }


def kairos_agent(
    state: MessagesState,
    config: RunnableConfig,
    store: BaseStore,
) -> dict:
    """
    Nodo principal del agente.
    1. Carga los 3 tipos de memoria del usuario (store + ChromaDB)
    2. Construye el prompt con el contexto del día
    3. Llama a Gemini con las tools disponibles
    """
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    request_data = config["configurable"].get("request_data", {})

    # Cargar memoria semántica: store + ChromaDB
    mem_sem_store = _cargar_memoria(store, id_usuario, "semantica")
    mem_sem_chroma = _enriquecer_desde_chroma(
        id_usuario, "semantica", "perfil metas hábitos productividad"
    )
    memoria_semantica = f"{mem_sem_store}\n{mem_sem_chroma}".strip()

    # Cargar memoria episódica: store + ChromaDB
    mem_epi_store = _cargar_memoria(store, id_usuario, "episodica")
    mem_epi_chroma = _enriquecer_desde_chroma(
        id_usuario, "episodica", "tareas completadas sueño actividad física reciente"
    )
    memoria_episodica = f"{mem_epi_store}\n{mem_epi_chroma}".strip()

    # Cargar memoria procedimental: store + ChromaDB
    mem_pro_store = _cargar_memoria(store, id_usuario, "procedimental")
    mem_pro_chroma = _enriquecer_desde_chroma(
        id_usuario, "procedimental", "preferencias horario bloques aceptados rechazados"
    )
    memoria_procedimental = f"{mem_pro_store}\n{mem_pro_chroma}".strip()

    # Formatear contexto del día
    ctx = _formatear_contexto(request_data)

    system_msg = PROMPT_SISTEMA.format(
        memoria_semantica=memoria_semantica,
        memoria_episodica=memoria_episodica,
        memoria_procedimental=memoria_procedimental,
        **ctx,
    )

    respuesta = modelo.bind_tools(
        todas_las_tools,
        parallel_tool_calls=False,
    ).invoke([SystemMessage(content=system_msg)] + state["messages"])

    return {"messages": [respuesta]}


def actualizar_semantica(
    state: MessagesState,
    config: RunnableConfig,
    store: BaseStore,
) -> dict:
    """Actualiza la memoria semántica con Trustcall y persiste en ChromaDB."""
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    namespace = ("semantica", id_usuario)

    items_existentes = store.search(namespace)
    memorias_existentes = (
        [(item.key, "ActualizarMemoria", item.value) for item in items_existentes]
        if items_existentes else None
    )

    instruccion = INSTRUCCION_ACTUALIZAR_MEMORIA.format(
        hora=datetime.now().isoformat()
    )
    resultado = extractor_semantica.invoke({
        "messages": [SystemMessage(content=instruccion)] + state["messages"][:-1],
        "existing": memorias_existentes,
    })

    for r, rmeta in zip(resultado["responses"], resultado["response_metadata"]):
        key = rmeta.get("json_doc_id", str(uuid.uuid4()))
        valor = r.model_dump(mode="json")
        store.put(namespace, key, valor)

        # Persistir también en ChromaDB para sobrevivir reinicios
        upsert_documento(
            doc_id=f"{id_usuario}_semantica_{key}",
            texto=valor.get("contenido", str(valor)),
            metadata={"id_usuario": id_usuario, "tipo_memoria": "semantica"},
        )

    tool_call_id = state["messages"][-1].tool_calls[0]["id"]
    return {"messages": [{"role": "tool", "content": "memoria semántica actualizada", "tool_call_id": tool_call_id}]}


def actualizar_episodica(
    state: MessagesState,
    config: RunnableConfig,
    store: BaseStore,
) -> dict:
    """Actualiza la memoria episódica con Trustcall y persiste en ChromaDB."""
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    namespace = ("episodica", id_usuario)

    items_existentes = store.search(namespace)
    memorias_existentes = (
        [(item.key, "ActualizarMemoria", item.value) for item in items_existentes]
        if items_existentes else None
    )

    instruccion = INSTRUCCION_ACTUALIZAR_MEMORIA.format(
        hora=datetime.now().isoformat()
    )
    resultado = extractor_semantica.invoke({
        "messages": [SystemMessage(content=instruccion)] + state["messages"][:-1],
        "existing": memorias_existentes,
    })

    for r, rmeta in zip(resultado["responses"], resultado["response_metadata"]):
        key = rmeta.get("json_doc_id", str(uuid.uuid4()))
        valor = r.model_dump(mode="json")
        store.put(namespace, key, valor)

        upsert_documento(
            doc_id=f"{id_usuario}_episodica_{key}",
            texto=valor.get("contenido", str(valor)),
            metadata={"id_usuario": id_usuario, "tipo_memoria": "episodica"},
        )

    tool_call_id = state["messages"][-1].tool_calls[0]["id"]
    return {"messages": [{"role": "tool", "content": "memoria episódica actualizada", "tool_call_id": tool_call_id}]}


def actualizar_procedimental(
    state: MessagesState,
    config: RunnableConfig,
    store: BaseStore,
) -> dict:
    """Actualiza la memoria procedimental con Trustcall y persiste en ChromaDB."""
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    namespace = ("procedimental", id_usuario)

    items_existentes = store.search(namespace)
    instrucciones_actuales = (
        items_existentes[0].value.get("contenido", "")
        if items_existentes else ""
    )

    instruccion = INSTRUCCION_PROCEDIMENTAL.format(
        instrucciones_actuales=instrucciones_actuales
    )
    resultado = extractor_procedimental.invoke({
        "messages": [SystemMessage(content=instruccion)] + state["messages"][:-1],
        "existing": (
            [(item.key, "ActualizarMemoria", item.value) for item in items_existentes]
            if items_existentes else None
        ),
    })

    for r, rmeta in zip(resultado["responses"], resultado["response_metadata"]):
        key = rmeta.get("json_doc_id", str(uuid.uuid4()))
        valor = r.model_dump(mode="json")
        store.put(namespace, key, valor)

        upsert_documento(
            doc_id=f"{id_usuario}_procedimental_{key}",
            texto=valor.get("contenido", str(valor)),
            metadata={"id_usuario": id_usuario, "tipo_memoria": "procedimental"},
        )

    tool_call_id = state["messages"][-1].tool_calls[0]["id"]
    return {"messages": [{"role": "tool", "content": "memoria procedimental actualizada", "tool_call_id": tool_call_id}]}


def enrutar_mensaje(
    state: MessagesState,
    config: RunnableConfig,
    store: BaseStore,
) -> Literal["actualizar_semantica", "actualizar_episodica",
             "actualizar_procedimental", "tools", "__end__"]:
    """
    Decide a dónde va el flujo después del nodo principal:
    - Si el agente quiere actualizar memoria → nodo correspondiente
    - Si el agente quiere usar una tool → ToolNode
    - Si no hay tool calls → END
    """
    from langgraph.graph import END

    mensaje = state["messages"][-1]
    if not hasattr(mensaje, "tool_calls") or not mensaje.tool_calls:
        return END

    nombre_tool = mensaje.tool_calls[0]["name"]

    if nombre_tool == "ActualizarMemoria":
        tipo = mensaje.tool_calls[0]["args"].get("tipo", "episodica")
        return {
            "semantica": "actualizar_semantica",
            "episodica": "actualizar_episodica",
            "procedimental": "actualizar_procedimental",
        }[tipo]

    return "tools"