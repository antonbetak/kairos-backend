from datetime import datetime
from datetime import time
from datetime import timedelta

from fastapi import FastAPI

from app.schemas import GeneratedBlock
from app.schemas import GenerateRequest
from app.schemas import GenerateResponse

app = FastAPI(title="Kairos Agent Service")


@app.get("/health")
def health():
    return {"service": "agent_service", "status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
def generate_schedule(request: GenerateRequest):
    inicio = datetime.combine(request.fecha, time(hour=9))
    bloques: list[GeneratedBlock] = []

    tareas = sorted(
        request.tareas,
        key=lambda tarea: (
            tarea.fecha_limite is None,
            tarea.fecha_limite.isoformat() if tarea.fecha_limite else "",
            tarea.prioridad,
        ),
    )

    for tarea in tareas[:4]:
        duracion = max(30, min(tarea.duracion_estimada_min or 60, 180))
        fin = inicio + timedelta(minutes=duracion)
        bloques.append(
            GeneratedBlock(
                titulo=tarea.titulo,
                descripcion=None,
                fecha_inicio=inicio,
                fecha_fin=fin,
                tipo=tarea.tipo or "tarea",
                razon="Bloque generado a partir de tareas activas",
            )
        )
        inicio = fin + timedelta(minutes=15)

    if not bloques:
        fin = inicio + timedelta(minutes=45)
        bloques.append(
            GeneratedBlock(
                titulo="Planificar el dia",
                descripcion="Revisar prioridades y preparar el siguiente bloque",
                fecha_inicio=inicio,
                fecha_fin=fin,
                tipo="planificacion",
                razon="No habia tareas activas suficientes para generar un horario",
            )
        )

    return GenerateResponse(
        id_usuario=request.id_usuario,
        fecha=request.fecha,
        es_fallback=not bool(request.tareas),
        bloques=bloques,
    )
