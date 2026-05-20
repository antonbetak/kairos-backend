from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.agent.nodes import (
    kairos_agent,
    actualizar_semantica,
    actualizar_episodica,
    actualizar_procedimental,
    enrutar_mensaje,
    tools_list,
)

logger = logging.getLogger(__name__)

store = (
    InMemoryStore()
)  # memoria de sesión (se complementa con ChromaDB para persistencia)
checkpointer = (
    MemorySaver()
)  # checkpointer para mantener el estado del grafo entre llamadas


def build_graph():
    builder = StateGraph(MessagesState)

    # Nodos
    builder.add_node("kairos_agent", kairos_agent)
    builder.add_node("tools", ToolNode(tools_list))
    builder.add_node("actualizar_semantica", actualizar_semantica)
    builder.add_node("actualizar_episodica", actualizar_episodica)
    builder.add_node("actualizar_procedimental", actualizar_procedimental)

    # Edges
    builder.add_edge(START, "kairos_agent")

    builder.add_conditional_edges(
        "kairos_agent",
        enrutar_mensaje,
        {
            "actualizar_semantica": "actualizar_semantica",
            "actualizar_episodica": "actualizar_episodica",
            "actualizar_procedimental": "actualizar_procedimental",
            "tools": "tools",
            END: END,
        },
    )

    # Después de ejecutar una tool o actualizar memoria → volver al agente
    builder.add_edge("tools", "kairos_agent")
    builder.add_edge("actualizar_semantica", "kairos_agent")
    builder.add_edge("actualizar_episodica", "kairos_agent")
    builder.add_edge("actualizar_procedimental", "kairos_agent")

    return builder.compile(checkpointer=checkpointer, store=store)


# Instancia global del grafo
graph = build_graph()
logger.info("Grafo LangGraph compilado")
