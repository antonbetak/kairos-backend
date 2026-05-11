from fastapi import FastAPI
from fastapi import Depends

from app.dependencies.auth import obtener_usuario_actual
from app.services.schedule_client import actualizar_horario
from app.services.schedule_client import crear_horario
from app.services.schedule_client import eliminar_horario
from app.services.schedule_client import listar_horarios
from app.services.schedule_client import obtener_horario
from app.services.task_client import crear_tarea
from app.services.task_client import listar_tareas

app = FastAPI(title="Kairos API Gateway")


@app.get("/health")
def health():
    return {"service": "api-gateway", "status": "ok"}


@app.get("/tasks")
async def obtener_tareas(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await listar_tareas(id_usuario)


@app.post("/tasks")
async def crear_nueva_tarea(datos: dict, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await crear_tarea(id_usuario, datos)


@app.post("/schedule")
async def crear_nuevo_horario(datos: dict, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await crear_horario(id_usuario, datos)


@app.get("/schedule")
async def obtener_horarios(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await listar_horarios(id_usuario)


@app.get("/schedule/{schedule_id}")
async def obtener_horario_por_id(schedule_id: str, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await obtener_horario(id_usuario, schedule_id)


@app.patch("/schedule/{schedule_id}")
async def actualizar_horario_por_id(
    schedule_id: str,
    datos: dict,
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    return await actualizar_horario(id_usuario, schedule_id, datos)


@app.delete("/schedule/{schedule_id}")
async def eliminar_horario_por_id(schedule_id: str, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await eliminar_horario(id_usuario, schedule_id)
