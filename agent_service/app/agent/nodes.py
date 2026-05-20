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

# Extractores Trustcall
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
    mems = store.search((tipo, id_usuario))
    if not mems:
        return f"Sin {tipo} registrada aún."
    return "\n".join(str(m.value) for m in mems)


def _enriquecer_desde_chroma(id_usuario: str, tipo: str, query: str) -> str:
    docs = buscar_por_tipo(id_usuario, tipo, query, n_results=3)
    if not docs:
        return ""
    return "\n".join(docs)


def _formatear_tarea(t: dict) -> str:
    linea = f"- [{t.get('tipo', 'tarea')}] {t.get('titulo', '')}"
    if t.get("fecha_limite"):
        linea += f" (límite: {t.get('fecha_limite')})"
    if t.get("duracion_estimada_min"):
        linea += f" (~{t.get('duracion_estimada_min')} min)"
    return linea


def _formatear_contexto(request_data: dict) -> dict:
    tareas = request_data.get("tareas", [])
    metas = request_data.get("metas", [])
    streaks = request_data.get("streaks", [])
    eventos = request_data.get("eventos_calendario", [])
    fecha = request_data.get("fecha", "hoy")

    tareas_str = (
        "\n".join(_formatear_tarea(t) for t in tareas) or "Sin tareas pendientes."
    )

    metas_str = (
        "\n".join(
            f"- {m.get('titulo')} ({m.get('progreso_pct', 0):.0f}% completada)"
            for m in metas
        )
        or "Sin metas activas."
    )

    streaks_str = (
        "\n".join(
            f"- {s.get('tipo_habito')}: racha actual {s.get('racha_actual')} días (máx {s.get('racha_maxima')})"
            for s in streaks
        )
        or "Sin streaks activos."
    )

    eventos_str = (
        "\n".join(
            f"- {e.get('titulo')} de {e.get('inicio')} a {e.get('fin')}"
            for e in eventos
        )
        or "Sin eventos en Google Calendar para hoy."
    )

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

    # Leer config backend
    id_usuario = "unknown"
    request_data = {}

    if config and "configurable" in config:
        id_usuario = config["configurable"].get("id_usuario", "unknown")
        request_data = config["configurable"].get("request_data", {})

    # Fallback para LangGraph Studio
    if not request_data:
        try:
            import json
            last_msg = state["messages"][-1].content
            parsed = json.loads(last_msg)

            request_data = parsed.get("request_data", {})
            id_usuario = request_data.get("id_usuario", id_usuario)

            logger.info("⚡ request_data leído desde mensaje (Studio)")
        except Exception:
            logger.info("⚠️ No se pudo parsear request_data desde mensaje")

    logger.info("ID USUARIO: %s", id_usuario)
    logger.info("REQUEST DATA FINAL: %s", request_data)

    mem_sem = _cargar_memoria(store, id_usuario, "semantica")
    mem_sem += "\n" + _enriquecer_desde_chroma(id_usuario, "semantica", "perfil metas hábitos")

    mem_epi = _cargar_memoria(store, id_usuario, "episodica")
    mem_epi += "\n" + _enriquecer_desde_chroma(id_usuario, "episodica", "tareas recientes")

    mem_pro = _cargar_memoria(store, id_usuario, "procedimental")
    mem_pro += "\n" + _enriquecer_desde_chroma(id_usuario, "procedimental", "preferencias horario")

    ctx = _formatear_contexto(request_data)

    system_msg = PROMPT_SISTEMA.format(
        memoria_semantica=mem_sem.strip(),
        memoria_episodica=mem_epi.strip(),
        memoria_procedimental=mem_pro.strip(),
        **ctx,
    )

    respuesta = modelo.bind_tools(
        todas_las_tools,
    ).invoke([SystemMessage(content=system_msg)] + state["messages"])

    return {"messages": [respuesta]}


def actualizar_semantica(state: MessagesState, config: RunnableConfig, store: BaseStore) -> dict:
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    namespace = ("semantica", id_usuario)

    resultado = extractor_semantica.invoke({
        "messages": [SystemMessage(content=INSTRUCCION_ACTUALIZAR_MEMORIA)] + state["messages"][:-1],
    })

    for r in resultado["responses"]:
        key = str(uuid.uuid4())
        valor = r.model_dump(mode="json")
        store.put(namespace, key, valor)

        upsert_documento(
            doc_id=f"{id_usuario}_sem_{key}",
            texto=valor.get("contenido", str(valor)),
            metadata={"id_usuario": id_usuario, "tipo_memoria": "semantica"},
        )

    return {"messages": [{"role": "tool", "content": "memoria semántica actualizada"}]}


def actualizar_episodica(state: MessagesState, config: RunnableConfig, store: BaseStore) -> dict:
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    namespace = ("episodica", id_usuario)

    resultado = extractor_semantica.invoke({
        "messages": [SystemMessage(content=INSTRUCCION_ACTUALIZAR_MEMORIA)] + state["messages"][:-1],
    })

    for r in resultado["responses"]:
        key = str(uuid.uuid4())
        valor = r.model_dump(mode="json")
        store.put(namespace, key, valor)

        upsert_documento(
            doc_id=f"{id_usuario}_epi_{key}",
            texto=valor.get("contenido", str(valor)),
            metadata={"id_usuario": id_usuario, "tipo_memoria": "episodica"},
        )

    return {"messages": [{"role": "tool", "content": "memoria episódica actualizada"}]}


def actualizar_procedimental(state: MessagesState, config: RunnableConfig, store: BaseStore) -> dict:
    id_usuario = config["configurable"].get("id_usuario", "unknown")
    namespace = ("procedimental", id_usuario)

    resultado = extractor_procedimental.invoke({
        "messages": [SystemMessage(content=INSTRUCCION_PROCEDIMENTAL)] + state["messages"][:-1],
    })

    for r in resultado["responses"]:
        key = str(uuid.uuid4())
        valor = r.model_dump(mode="json")
        store.put(namespace, key, valor)

        upsert_documento(
            doc_id=f"{id_usuario}_proc_{key}",
            texto=valor.get("contenido", str(valor)),
            metadata={"id_usuario": id_usuario, "tipo_memoria": "procedimental"},
        )

    return {"messages": [{"role": "tool", "content": "memoria procedimental actualizada"}]}


def enrutar_mensaje(
    state: MessagesState,
    config: RunnableConfig,
    store: BaseStore,
) -> Literal["actualizar_semantica", "actualizar_episodica", "actualizar_procedimental", "tools", "__end__"]:

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
