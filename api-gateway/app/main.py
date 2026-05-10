from fastapi import FastAPI
from fastapi import Depends

from app.dependencies.auth import obtener_usuario_actual
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
