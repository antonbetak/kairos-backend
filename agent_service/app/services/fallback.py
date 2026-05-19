import logging
from datetime import datetime, timedelta

from app.schemas import GenerateRequest, GenerateResponse, BloqueAgente

logger = logging.getLogger(__name__)

# Slots de tiempo predefinidos por tipo de actividad
# La lógica: hábitos en la mañana, tareas de trabajo en el día, libre al final
SLOTS_PREDETERMINADOS = [
    {"hora_inicio": 7,  "hora_fin": 8,  "tipo_preferido": "habito"},
    {"hora_inicio": 9,  "hora_fin": 11, "tipo_preferido": "tarea"},
    {"hora_inicio": 11, "hora_fin": 13, "tipo_preferido": "tarea"},
    {"hora_inicio": 15, "hora_fin": 17, "tipo_preferido": "tarea"},
    {"hora_inicio": 17, "hora_fin": 18, "tipo_preferido": "habito"},
]

MAX_BLOQUES_DIA = 5


def generar_horario_fallback(request: GenerateRequest) -> GenerateResponse:
    """
    Genera un horario básico sin RAG cuando el usuario no tiene
    suficiente historial en ChromaDB.

    Lógica:
    1. Streaks con racha_actual > 0 tienen prioridad (no romper la racha)
    2. Tareas con fecha_limite más cercana van primero
    3. Se asignan a slots predeterminados según tipo
    """
    logger.info("Generando horario fallback para usuario %s", request.id_usuario)

    fecha = request.fecha
    bloques: list[BloqueAgente] = []

    # Priorizar streaks activos (racha > 0) para no romperlos
    habitos_prioritarios = [
        s for s in request.streaks if s.racha_actual > 0
    ]

    # Tareas ordenadas por fecha_limite ascendente (las más urgentes primero)
    tareas_ordenadas = sorted(
        request.tareas,
        key=lambda t: t.fecha_limite or datetime(9999, 12, 31),
    )

    # Mezclar: primero hábitos prioritarios, luego tareas
    items_a_programar = []
    for streak in habitos_prioritarios[:2]:  # máx 2 hábitos por día en fallback
        items_a_programar.append(("habito", streak.tipo_habito, 30))

    for tarea in tareas_ordenadas:
        if len(items_a_programar) >= MAX_BLOQUES_DIA:
            break
        duracion = tarea.duracion_estimada_min or 60
        items_a_programar.append(("tarea", tarea.titulo, duracion))

    # Asignar slots
    slot_idx = 0
    for tipo_item, titulo_item, duracion_item in items_a_programar:
        if slot_idx >= len(SLOTS_PREDETERMINADOS):
            break

        slot = SLOTS_PREDETERMINADOS[slot_idx]
        fecha_inicio = datetime(
            fecha.year, fecha.month, fecha.day,
            slot["hora_inicio"], 0
        )
        fecha_fin = fecha_inicio + timedelta(minutes=duracion_item)

        # Si la actividad no cabe en el slot, la recortamos al fin del slot
        limite_slot = datetime(
            fecha.year, fecha.month, fecha.day,
            slot["hora_fin"], 0
        )
        if fecha_fin > limite_slot:
            fecha_fin = limite_slot

        bloques.append(BloqueAgente(
            titulo=titulo_item,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo=tipo_item,
            razon="Horario generado con heurísticas básicas. Mejorará con el tiempo.",
        ))
        slot_idx += 1

    return GenerateResponse(
        id_usuario=request.id_usuario,
        fecha=fecha,
        bloques=bloques,
        es_fallback=True,
    )