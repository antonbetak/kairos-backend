from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies.auth import obtener_usuario_actual
from app.routes.proxy import router as proxy_router
from app.services.notifications_client import crear_notificacion
from app.services.notifications_client import listar_notificaciones
from app.services.notifications_client import marcar_notificacion_leida
from app.services.notifications_client import marcar_todas_notificaciones_leidas
from app.services.schedule_client import actualizar_horario
from app.services.schedule_client import crear_horario
from app.services.schedule_client import eliminar_horario
from app.services.schedule_client import listar_horarios
from app.services.schedule_client import obtener_horario
from app.services.stats_client import listar_logros
from app.services.stats_client import obtener_estadisticas
from app.services.stats_client import obtener_racha
from app.services.task_client import crear_tarea
from app.services.task_client import actualizar_tarea
from app.services.task_client import eliminar_tarea
from app.services.task_client import listar_tareas


settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(settings.app_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    yield
    logger.info("Stopping %s", settings.app_name)


app = FastAPI(
    title="Kairos API Gateway",
    version="1.0.0",
    description="Central gateway for routing requests to internal microservices.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(proxy_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/tasks")
async def obtener_tareas(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await listar_tareas(id_usuario)


@app.post("/tasks")
async def crear_nueva_tarea(datos: dict, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await crear_tarea(id_usuario, datos)


@app.patch("/tasks/{id_tarea}")
async def actualizar_tarea_por_id(
    id_tarea: str,
    datos: dict,
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    return await actualizar_tarea(id_usuario, id_tarea, datos)


@app.delete("/tasks/{id_tarea}")
async def eliminar_tarea_por_id(id_tarea: str, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await eliminar_tarea(id_usuario, id_tarea)


@app.post("/schedule")
async def crear_nuevo_horario(datos: dict, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await crear_horario(id_usuario, datos)


@app.get("/schedule")
async def obtener_horarios(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await listar_horarios(id_usuario)


@app.get("/schedule/{schedule_id}")
async def obtener_horario_por_id(
    schedule_id: str, usuario=Depends(obtener_usuario_actual)
):
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
async def eliminar_horario_por_id(
    schedule_id: str, usuario=Depends(obtener_usuario_actual)
):
    id_usuario = usuario["id_usuario"]
    return await eliminar_horario(id_usuario, schedule_id)


@app.get("/estadisticas")
async def consultar_estadisticas(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await obtener_estadisticas(id_usuario)


@app.get("/rachas/{tipo}")
async def consultar_racha(tipo: str, usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await obtener_racha(id_usuario, tipo)


@app.get("/logros")
async def consultar_logros(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await listar_logros(id_usuario)


@app.get("/notificaciones")
async def obtener_notificaciones(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await listar_notificaciones(id_usuario)


@app.post("/notificaciones")
async def crear_nueva_notificacion(
    datos: dict, usuario=Depends(obtener_usuario_actual)
):
    id_usuario = usuario["id_usuario"]
    return await crear_notificacion(id_usuario, datos)


@app.patch("/notificaciones/{notificacion_id}/leer")
async def leer_notificacion(
    notificacion_id: str, usuario=Depends(obtener_usuario_actual)
):
    id_usuario = usuario["id_usuario"]
    return await marcar_notificacion_leida(id_usuario, notificacion_id)


@app.patch("/notificaciones/leer-todas")
async def leer_todas_notificaciones(usuario=Depends(obtener_usuario_actual)):
    id_usuario = usuario["id_usuario"]
    return await marcar_todas_notificaciones_leidas(id_usuario)
