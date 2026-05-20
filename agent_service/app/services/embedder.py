import logging
from datetime import datetime, timezone

from app.db.chroma import upsert_documento

logger = logging.getLogger(__name__)


def registrar_tarea_completada(evento: dict) -> None:
    """
    Cuando se completa una tarea, guardamos un documento de comportamiento:
    a qué hora la completó, de qué tipo era, cuánto tardó vs estimado.
    """
    id_usuario = evento.get("id_usuario")
    if not id_usuario:
        return

    titulo = evento.get("titulo", "sin título")
    tipo = evento.get("tipo", "tarea")
    fecha_ini = evento.get("fecha_inicio")
    fecha_fin = evento.get("fecha_fin")
    hora_comp = evento.get("completada_en") or datetime.now(timezone.utc).isoformat()

    # Construir texto descriptivo que el LLM puede interpretar como contexto
    texto = (
        f"El usuario completó una actividad de tipo '{tipo}' llamada '{titulo}'. "
        f"Estaba programada de {fecha_ini} a {fecha_fin}. "
        f"Fue marcada como completada en: {hora_comp}."
    )

    doc_id = f"{id_usuario}_completada_{evento.get('id_tarea', hora_comp)}"
    metadata = {
        "id_usuario": id_usuario,
        "tipo": "tarea_completada",
        "tipo_actividad": tipo,
        "timestamp": hora_comp,
    }

    upsert_documento(doc_id, texto, metadata)
    logger.info("Patrón registrado: tarea_completada para usuario %s", id_usuario)


def registrar_tarea_abandonada(evento: dict) -> None:
    """
    Cuando se abandona una tarea, guardamos el patrón de abandono:
    tipo de actividad, hora del día, posible contexto de sobrecarga.
    """
    id_usuario = evento.get("id_usuario")
    if not id_usuario:
        return

    titulo = evento.get("titulo", "sin título")
    tipo = evento.get("tipo", "tarea")
    timestamp = evento.get("timestamp") or datetime.now(timezone.utc).isoformat()

    texto = (
        f"El usuario abandonó una actividad de tipo '{tipo}' llamada '{titulo}'. "
        f"Esto ocurrió en: {timestamp}. "
        f"Este patrón puede indicar sobrecarga o baja motivación en ese tipo de actividad."
    )

    doc_id = f"{id_usuario}_abandonada_{evento.get('id_tarea', timestamp)}"
    metadata = {
        "id_usuario": id_usuario,
        "tipo": "tarea_abandonada",
        "tipo_actividad": tipo,
        "timestamp": timestamp,
    }

    upsert_documento(doc_id, texto, metadata)
    logger.info("Patrón registrado: tarea_abandonada para usuario %s", id_usuario)


def registrar_resumen_estadisticas(evento: dict) -> None:
    """
    Cuando el stats-service publica un resumen periódico,
    lo embeddemos como conocimiento de productividad del usuario.
    """
    id_usuario = evento.get("id_usuario")
    if not id_usuario:
        return

    periodo = evento.get("periodo", "diario")
    fecha_inicio = evento.get("fecha_inicio")
    total_actividades = evento.get("total_actividades", 0)
    completadas = evento.get("completadas", 0)
    tiempo_productivo = evento.get("tiempo_productivo_min", 0)
    puntuacion = evento.get("puntuacion_productividad", 0.0)
    timestamp = evento.get("timestamp") or datetime.now(timezone.utc).isoformat()

    tasa = round(
        (completadas / total_actividades * 100) if total_actividades > 0 else 0, 1
    )

    texto = (
        f"Resumen {periodo} del usuario (período: {fecha_inicio}): "
        f"Tuvo {total_actividades} actividades, completó {completadas} ({tasa}%). "
        f"Tiempo productivo: {tiempo_productivo} minutos. "
        f"Puntuación de productividad: {puntuacion}/10. "
        f"Este resumen refleja su capacidad de carga y consistencia en ese período."
    )

    doc_id = f"{id_usuario}_resumen_{periodo}_{fecha_inicio}"
    metadata = {
        "id_usuario": id_usuario,
        "tipo": "resumen_productividad",
        "periodo": periodo,
        "timestamp": timestamp,
    }

    upsert_documento(doc_id, texto, metadata)
    logger.info("Patrón registrado: resumen_%s para usuario %s", periodo, id_usuario)
