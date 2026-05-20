from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI
from fastapi import Header
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.dependencies.auth import obtener_usuario_actual
from app.routes.proxy import router as proxy_router
from app.services.notifications_client import crear_notificacion
from app.services.notifications_client import listar_notificaciones
from app.services.notifications_client import marcar_notificacion_leida
from app.services.notifications_client import marcar_todas_notificaciones_leidas
from app.services.schedule_client import aceptar_horario
from app.services.schedule_client import actualizar_horario
from app.services.schedule_client import crear_horario
from app.services.schedule_client import eliminar_horario
from app.services.schedule_client import generar_horario
from app.services.schedule_client import listar_horarios
from app.services.schedule_client import obtener_horario
from app.services.schedule_client import rechazar_horario
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


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


# Note: the gateway obtains Google access tokens server-side when proxying requests
# (see `app.routes.proxy._try_fetch_google_header`) using the authenticated
# user's Clerk id. The previously exposed internal token endpoint was removed
# to avoid exposing token retrieval over HTTP.


@app.get("/tasks")
async def obtener_tareas(
    authorization: str | None = Header(default=None),
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await listar_tareas(authorization, x_google_token, x_google_refresh)


@app.post("/tasks")
async def crear_nueva_tarea(
    datos: dict,
    authorization: str | None = Header(default=None),
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await crear_tarea(authorization, datos, x_google_token, x_google_refresh)


@app.patch("/tasks/{id_tarea}")
async def actualizar_tarea_por_id(
    id_tarea: str,
    datos: dict,
    authorization: str | None = Header(default=None),
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await actualizar_tarea(
        authorization,
        id_tarea,
        datos,
        x_google_token,
        x_google_refresh,
    )


@app.delete("/tasks/{id_tarea}")
async def eliminar_tarea_por_id(
    id_tarea: str,
    authorization: str | None = Header(default=None),
    x_google_token: str | None = Header(default=None, alias="X-Google-Token"),
    x_google_refresh: str | None = Header(default=None, alias="X-Google-Refresh"),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await eliminar_tarea(
        authorization,
        id_tarea,
        x_google_token,
        x_google_refresh,
    )


@app.post("/schedule")
async def crear_nuevo_horario(
    datos: dict,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await crear_horario(authorization, datos)


@app.post("/schedule/generate")
async def generar_horario_propuesto(
    datos: dict,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await generar_horario(authorization, datos)


@app.get("/schedule")
async def obtener_horarios(
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await listar_horarios(authorization)


@app.get("/schedule/{schedule_id}")
async def obtener_horario_por_id(
    schedule_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await obtener_horario(authorization, schedule_id)


@app.patch("/schedule/{schedule_id}")
async def actualizar_horario_por_id(
    schedule_id: str,
    datos: dict,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await actualizar_horario(authorization, schedule_id, datos)


@app.patch("/schedule/{schedule_id}/accept")
async def aceptar_horario_por_id(
    schedule_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await aceptar_horario(authorization, schedule_id)


@app.delete("/schedule/{schedule_id}/reject")
async def rechazar_horario_por_id(
    schedule_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await rechazar_horario(authorization, schedule_id)


@app.delete("/schedule/{schedule_id}")
async def eliminar_horario_por_id(
    schedule_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    return await eliminar_horario(authorization, schedule_id)


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
async def obtener_notificaciones(
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await listar_notificaciones(authorization)


@app.post("/notificaciones")
async def crear_nueva_notificacion(
    datos: dict,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await crear_notificacion(authorization, datos)


@app.patch("/notificaciones/{notificacion_id}/leer")
async def leer_notificacion(
    notificacion_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await marcar_notificacion_leida(authorization, notificacion_id)


@app.patch("/notifications/{notificacion_id}/leer")
async def leer_notification_alias_legacy(
    notificacion_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await marcar_notificacion_leida(authorization, notificacion_id)


@app.patch("/notificaciones/leer-todas")
async def leer_todas_notificaciones(
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await marcar_todas_notificaciones_leidas(authorization)


@app.patch("/notifications/leer-todas")
async def leer_todas_notifications_alias_legacy(
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await marcar_todas_notificaciones_leidas(authorization)


@app.get("/notifications")
async def obtener_notifications_alias(
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await listar_notificaciones(authorization)


@app.post("/notifications")
async def crear_notifications_alias(
    datos: dict,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await crear_notificacion(authorization, datos)


@app.patch("/notifications/{notificacion_id}/read")
async def leer_notification_alias(
    notificacion_id: str,
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await marcar_notificacion_leida(authorization, notificacion_id)


@app.patch("/notifications/read-all")
async def leer_todas_notifications_alias(
    authorization: str | None = Header(default=None),
    usuario=Depends(obtener_usuario_actual),
):
    id_usuario = usuario["id_usuario"]
    if not authorization:
        authorization = f"Bearer {id_usuario}"
    return await marcar_todas_notificaciones_leidas(authorization)


app.include_router(proxy_router)
