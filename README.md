# API Gateway

El **API Gateway** es el unico punto de entrada expuesto. Todos los microservicios quedan en red interna.

- Base URL: `http://localhost:8000`
- Health del gateway: `GET /health`
- Ready del gateway: `GET /ready`

# Endpoints por microservicio (via gateway)

- `google_auth`: `/auth/google/login`, `/auth/google/callback`, `/auth/google/refresh`, `/auth/google/me`.
- `google_auth` (Clerk sync): `/auth/google/clerk/session`.
- `auth_service`: `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/verify`.
- `calendar_service`: `/google/calendars`, `/google/events` (GET/POST), `/google/events/{id}` (PUT/DELETE), `/google/refresh`, `/device/calendars` (GET/POST), `/device/events` (GET/POST).
- `googlefit_service`: `/fit/me`.
- `activity_service`: `/activity/me`, `/activity/feed`, `/activity/events`, `/activity/friends`, `/activity/friends/request`, `/activity/friends/{id}/accept`, `/activity/invites`, `/activity/events/{id}/react`, `/activity/events/{id}/comments`.
- `task_service`: `/tasks` (GET/POST), `/tasks/{id}` (PATCH/DELETE).
- `schedule_service`: `/schedule` (GET/POST), `/schedule/{id}` (GET/PATCH/DELETE).
- `stt_service`: `/stt/*` (ej. `/stt/health`).
- `notifications_service`: `/notificaciones` (GET/POST), `/notificaciones/{id}/leer` (PATCH), `/notificaciones/leer-todas` (PATCH). Alias en gateway: `/notifications`, `/notifications/{id}/read`, `/notifications/read-all`.
- `stats_service`: `/stats/*` (ej. `/stats/health`).
- `agent_service`: `/agent/*` (ej. `/agent/health`).
- Healths via gateway: `/health/google_auth`, `/health/calendar`, `/health/fit`, `/health/auth_service`, `/health/activity_service`, `/health/schedule_service`, `/health/task_service`, `/health/stt_service`, `/health/notifications_service`, `/health/stats_service`, `/health/agent_service`.

Nota: `/tasks`, `/schedule/*`, `/activity/*`, `/notificaciones*` y `/notifications*` requieren `Authorization: Bearer <token>` emitido por `auth_service`.
Nota: `auth_service` y `google_auth` son servicios distintos; sus rutas no colisionan.

# Auditoria de ramas del API Gateway

## Mapa de conflictos

| Aspecto | Rama A (feature/api_gateway) | Rama B (feature/integracion-auth-task-schedule-gateway) | Decision propuesta |
| --- | --- | --- | --- |
| Rutas duplicadas | `/health`, `/ready`, `/health/{service}`, `/ready/{service}`, `/auth/google/*`, `/google/*`, `/device/*`, `/fit/*` | `/health`, `/tasks`, `/schedule`, `/schedule/{id}` | Mantener ambas familias de rutas; `/health`
| Middlewares | CORS configurable via `CORS_ORIGINS` | Sin CORS | Conservar CORS aplicar dependencia de auth solo en rutas protegidas |
| Puertos | Gateway expone `API_GATEWAY_PORT` y usa URLs por env | URLs hardcodeadas a `auth_service`, `schedule_service`, `task_service`; no config de puerto en gateway | Centralizar URLs y puertos en `config.py` |
| Naming conventions | `google_auth`, `calendar-service`, `googlefit_service` | `auth_service`, `schedule_service`, `task_service` | Estandarizar nombres internos en config (snake_case) y permitir override por env. |
| Manejo de errores | Proxy con `HTTP 502` si falla upstream; reenvia status/headers | `response.json()` sin validar status; auth devuelve `401` en dependencia | Mantener comportamiento por ruta para compatibilidad; documentar que tasks/schedule responden JSON directo. |
| Autenticacion | No valida tokens | Dependencia `obtener_usuario_actual` con `Authorization: Bearer` | Conservar auth en `/tasks` y `/schedule/*`; no exigir auth en rutas de Google. |
| Formato de respuesta | Passthrough completo (status, headers, body) | JSON directo (sin status upstream) | Mantener passthrough para rutas proxy; mantener JSON directo para tasks/schedule. |

## Inventario de servicios

- `google_auth` -> `/auth/google/*` -> `http://google_auth:8000`
- `calendar_service` -> `/google/*`, `/device/*` -> `http://calendar-service:8000`
- `googlefit_service` -> `/fit/*` -> `http://googlefit_service:8000`
- `auth_service` -> `/auth/*` -> `http://auth_service:8000`
- `activity_service` -> `/activity/*` -> `http://activity_service:8000`
- `task_service` -> `/tasks` -> `http://task_service:8000`
- `schedule_service` -> `/schedule`, `/schedule/{id}` -> `http://schedule_service:8000`
- `stt_service` -> `/stt/*` -> `http://stt_service:8000`
- `notifications_service` -> `/notificaciones*` (alias `/notifications*` en gateway) -> `http://notifications_service:8000`
- `stats_service` -> `/stats/*` -> `http://stats_service:8000`
- `agent_service` -> `/agent/*` -> `http://agent_service:8000`

# Como correr el proyecto

1. Copia variables de entorno base:

```bash
copy .env.example .env
```

2. Ajusta secretos y credenciales en `.env`.

# Kairos — Backend (Monorepo)

Resumen breve del repositorio y guía principal. Este README contiene la información más relevante para entender, instalar y ejecutar el backend de Kairos.

**Base URL (gateway):** `http://localhost:8000`

**Estructura de alto nivel:** cada microservicio vive en una carpeta raíz (`auth_service`, `google_auth`, `calendar_service`, `activity_service`, `task_service`, `schedule_service`, `notifications_service`, `googlefit_service`, `stats_service`, `agent_service`, `stt_service`) y el único punto de entrada expuesto al host es el API Gateway.

**Nota importante:** muchas rutas expuestas por el gateway requieren autenticación con un `JWT` emitido por `auth_service`. Para integraciones con Google Calendar/Fit se usan tokens de Google (`X-Google-Token`).

## 1. Nombre del proyecto

- Kairos — Backend

## 2. Nombre del equipo / startup

- Equipo: Kairos (equipo de backend)

## 3. Integrantes y roles

- Moisés Rodríguez — Backend / Integración Google (ejemplo).  
- [Rellenar con integrantes reales y roles]

> Edita esta sección con los nombres y roles concretos del equipo.

## 4. Problema que resolvemos

Las personas necesitan una plataforma ligera que centralice tareas, horarios, actividad social y notificaciones, sincronizando opcionalmente con servicios de Google (Calendar, Fit) y enviando notificaciones, métricas y progreso compartido de forma asíncrona entre microservicios.

## 5. Solución

Conjunto de microservicios desacoplados que se comunican mediante RabbitMQ para eventos de dominio (p. ej. tareas creadas, tareas completadas, tareas vencidas, horarios creados). Un API Gateway expone los endpoints al cliente y actúa como proxy hacia los servicios internos.

## 6. Arquitectura general

Arquitectura basada en microservicios + bus de eventos (RabbitMQ). El gateway es el único servicio con puertos publicados, el resto queda en la red interna de Docker Compose.

El `activity_service` concentra la parte social de Kairos: registra actividad del usuario, arma el feed de progreso, gestiona amistades e invitaciones, y permite reacciones/comentarios sobre eventos. Además consume eventos de dominio desde RabbitMQ para convertir acciones relevantes, como tareas completadas o bloques terminados, en actividad visible según la privacidad configurada.

Diagrama y más detalles en: [docs/arquitectura.md](docs/arquitectura.md)

## 7. Tecnologías utilizadas

- Python 3.x + FastAPI
- PostgreSQL (cada servicio que necesita persistencia)
- Redis (para caché y listas, p. ej. `redis_client` en servicios)
- RabbitMQ (event bus)
- Docker & Docker Compose
- Google APIs (OAuth2 / Calendar / Fitness)

## 8. Instrucciones de instalación

1. Copia archivo de ejemplo de variables de entorno:

```bash
copy .env.example .env
```

2. Ajusta valores en `.env` (secretos, URLs, credenciales Google, claves JWT, base de datos).
3. Construye y levanta el stack (desarrollo):

```bash
docker compose -f docker-compose.dev.yml up --build
```

Para el stack completo (producción/staging):

```bash
docker compose up --build
```

## 9. Instrucciones de ejecución (local)

- Levantar con Docker Compose (ver arriba).  
- Para ejecutar un servicio individual en desarrollo (ej. `auth_service`), activa el entorno virtual del servicio y corre `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.

## 10. Variables de entorno

- Revisa `.env.example` para la lista de variables necesarias. Entre las más relevantes:
  - `API_GATEWAY_PORT` — puerto del gateway (por defecto 8000)
  - `DATABASE_URL` — cadena Postgres por servicio
  - `JWT_SECRET`, `JWT_ALGORITHM` — configuración de tokens
  - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — credenciales Google
  - `RABBITMQ_URL` — URL de RabbitMQ

  ### Clerk + Google Auth (actualizado)

  - El login principal del cliente se realiza con Clerk.
  - Clerk solo maneja autenticación y sesión; el frontend no debe obtener ni decodificar tokens de Google.
  - El backend obtiene el Google OAuth access token directamente desde Clerk Backend API usando `CLERK_SECRET_KEY` cuando necesita llamar a Google APIs.
  - El frontend no debe enviar ni almacenar `X-Google-Token`/`google_access_token`.

## 11. Endpoints principales

Resumen de endpoints por servicio (a través del gateway):

- Auth (propio): `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/verify`  
- Google OAuth: `/auth/google/login`, `/auth/google/callback`, `/auth/google/refresh`, `/auth/google/me`  
- Calendar: `/google/calendars`, `/google/events` (GET/POST), `/google/events/{id}` (PUT/DELETE)  
- Google Fit: `/fit/me`  
- Activity: `/activity/me`, `/activity/feed`, `/activity/events`, `/activity/friends`, `/activity/friends/request`, `/activity/friends/{id}/accept`, `/activity/invites`, `/activity/events/{id}/react`, `/activity/events/{id}/comments`  
- Tasks: `/tasks` (GET/POST), `/tasks/{id}` (PATCH/DELETE)  
- Schedule: `/schedule` (GET/POST), `/schedule/{id}` (GET/PATCH/DELETE)  
- Notifications: `/notificaciones` (GET/POST), `/notificaciones/{id}/leer` (PATCH) — alias `/notifications` en gateway  

Detalles y ejemplos en: [docs/api.md](docs/api.md)

## 12. Eventos principales (AMQP)

Los eventos de dominio que circulan por RabbitMQ:

- `Task.Created` — publicado por `task_service`. Consumidores: `notifications_service`, `schedule_service`, `stats_service`, `calendar_service` (si llega `X-Google-Token`).
- `Task.Completed` — publicado por `task_service`. Consumidores: `notifications_service`, `stats_service`, `activity_service`.
- `Task.DueWarning` — publicado por `task_service`. Consumidor: `notifications_service`.
- `Task.Due` — publicado por `task_service`. Consumidor: `notifications_service`.
- `Schedule.Created`, `Schedule.Updated`, `Schedule.Error` — publicados por `schedule_service`. Consumidores: `notifications_service`, `stats_service`, `calendar_service`.
- `bloque.completado` — evento de negocio adicional. Consumidor: `activity_service`.
- `logro.desbloqueado`, `racha.actualizada` — eventos de progreso social. Consumidor: `activity_service`.

Descripción detallada de contratos y payloads en: [docs/eventos.md](docs/eventos.md)

## 13. Evidencias de pruebas

Pruebas manuales y pasos reproducibles están documentados en: [docs/pruebas.md](docs/pruebas.md)

## 14. Fallas simuladas

Escenarios y cómo reproducir fallas controladas (p. ej. caída de RabbitMQ, error en Google API, expiración de tokens) en: [docs/fallas-simuladas.md](docs/fallas-simuladas.md)

## 15. Lecciones aprendidas

- Preferir comunicación por eventos para desacoplar microservicios críticos.
- Exponer un único gateway facilita CORS y seguridad, pero requiere manejo centralizado de timeouts y errores.
- Mantener contratos de eventos y versiones ayuda a evolucionar consumidores sin rupturas.

## 16. Documentación técnica adicional

Todos los documentos técnicos se encuentran en la carpeta `docs/`:

- [docs/requerimientos.md](docs/requerimientos.md)
- [docs/arquitectura.md](docs/arquitectura.md)
- [docs/modelo-datos.md](docs/modelo-datos.md)
- [docs/eventos.md](docs/eventos.md)
- [docs/api.md](docs/api.md)
- [docs/pruebas.md](docs/pruebas.md)
- [docs/fallas-simuladas.md](docs/fallas-simuladas.md)
- [docs/decisiones-tecnicas.md](docs/decisiones-tecnicas.md)

----

Si quieres que rellene los nombres de integrantes, ejemplos de payloads concretos o que genere diagramas (mermaid), dime qué prefieres y lo completo.
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_URI`
- `GOOGLE_SCOPE` (debe incluir `https://www.googleapis.com/auth/calendar`)

## Endpoints del Calendar Service

- `GET /google/calendars`
- `GET /google/events`
- `POST /google/events`
- `PUT /google/events/{id}`
- `DELETE /google/events/{id}`
- `POST /google/refresh`
- `GET /device/calendars`
- `POST /device/calendars`
- `GET /device/events`
- `POST /device/events`
- `GET /health`
- `GET /ready`


### Listar calendarios

GET `http://localhost:8000/google/calendars`

Headers:

- `Authorization: Bearer <JWT>` (opcional)
- `X-Google-Token: <access_token>` o `Authorization: Bearer <access_token>` (obligatorio cuando accedes Google Calendar)

### Listar eventos

GET `http://localhost:8000/google/events?calendar_id=primary&time_min=2025-01-01T00:00:00Z&time_max=2025-12-31T23:59:59Z`

Headers:

- `Authorization: Bearer <JWT>` (opcional)
- `X-Google-Token: <access_token>` (obligatorio)

### Crear evento

POST `http://localhost:8000/google/events`

Headers:

- `Authorization: Bearer <JWT>` (opcional)
- `X-Google-Token: <access_token>` (obligatorio)

Body:

```json
{
  "calendar_id": "primary",
  "summary": "Reunión de prueba",
  "description": "Evento creado desde API",
  "location": "Zoom",
  "start": {"dateTime": "2026-05-10T15:00:00-06:00"},
  "end": {"dateTime": "2026-05-10T16:00:00-06:00"},
  "attendees": [{"email": "invitado@example.com"}],
  "reminders": [{"method": "popup", "minutes": 30}]
}
```

### Actualizar evento

PUT `http://localhost:8000/google/events/{event_id}`

Body (parcial):

```json
{
  "calendar_id": "primary",
  "summary": "Reunión actualizada"
}
```

### Eliminar evento

DELETE `http://localhost:8000/google/events/{event_id}?calendar_id=primary`

### Refrescar access_token

POST `http://localhost:8000/google/refresh`

Body:

```json
{
  "refresh_token": "<refresh_token>"
}

## Device Calendar 

La lectura/creacion de eventos locales se hace en el dispositivo con Expo .
El backend solo recibe la informacion para sincronizar y mantener aislamiento por usuario.

### Instalacion en app Expo

```bash
npx expo install expo-calendar
```




### Probar endpoints de dispositivo

1) Sincroniza calendarios locales:

POST `http://localhost:8000/device/calendars`

Headers:

- `Authorization: Bearer <JWT>`

Body:

```json
{
  "calendars": [
    {"id": "local-1", "title": "Personal", "source": "device"}
  ]
}
```

2) Leer calendarios sincronizados:

GET `http://localhost:8000/device/calendars`

Headers:

- `Authorization: Bearer <JWT>`

3) Crear evento local (client-side) y notificar al backend:

POST `http://localhost:8000/device/events`

Headers:

- `Authorization: Bearer <JWT>`

Body:

```json
{
  "calendar_id": "local-1",
  "title": "Evento local",
  "start_date": "2026-05-10T15:00:00-06:00",
  "end_date": "2026-05-10T16:00:00-06:00",
  "notes": "Creado desde Expo Calendar",
  "location": "Dispositivo"
}
```

4) Leer eventos sincronizados:

GET `http://localhost:8000/device/events?calendar_id=local-1`

Headers:

- `Authorization: Bearer <JWT>`
```

## Ejecutar el Calendar Service

Dev:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up --build calendar-service
```

Prod:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build -d calendar-service
```

# Google Fit Service

Microservicio independiente para consultar datos de Google Fit en una sola respuesta.

## Google Cloud Console (Fitness API)

1. Ve a **APIs y servicios > Biblioteca**.
2. Busca **Fitness API** y pulsa **HABILITAR**.
3. En la pantalla de consentimiento, agrega estos scopes (lectura y escritura):
  - `https://www.googleapis.com/auth/fitness.sleep.write`
  - `https://www.googleapis.com/auth/fitness.sleep.read`
  - `https://www.googleapis.com/auth/fitness.oxygen_saturation.write`
  - `https://www.googleapis.com/auth/fitness.oxygen_saturation.read`
  - `https://www.googleapis.com/auth/fitness.nutrition.write`
  - `https://www.googleapis.com/auth/fitness.nutrition.read`
  - `https://www.googleapis.com/auth/fitness.location.write`
  - `https://www.googleapis.com/auth/fitness.location.read`
  - `https://www.googleapis.com/auth/fitness.heart_rate.write`
  - `https://www.googleapis.com/auth/fitness.heart_rate.read`
  - `https://www.googleapis.com/auth/fitness.body.write`
  - `https://www.googleapis.com/auth/fitness.body.read`
  - `https://www.googleapis.com/auth/fitness.body_temperature.write`
  - `https://www.googleapis.com/auth/fitness.body_temperature.read`
  - `https://www.googleapis.com/auth/fitness.blood_pressure.write`
  - `https://www.googleapis.com/auth/fitness.blood_pressure.read`
  - `https://www.googleapis.com/auth/fitness.blood_glucose.write`
  - `https://www.googleapis.com/auth/fitness.blood_glucose.read`
  - `https://www.googleapis.com/auth/fitness.activity.write`
  - `https://www.googleapis.com/auth/fitness.activity.read`

**Nota**: El `google_auth` debe solicitar estos scopes en `GOOGLE_SCOPE` para que el token tenga permisos de Fit.

## Seguridad

El endpoint `/fit/me` requiere un **access_token de Google**.

Headers:

- `X-Google-Token: <access_token>`
- `X-Google-Refresh: <refresh_token>` (opcional)

## Variables de entorno (Google Fit)

- `GOOGLE_FIT_PORT`
- `GOOGLE_FIT_API_BASE`
- `GOOGLE_FIT_SCOPES` (usar scopes de lectura y escritura)
- `FIT_BUCKET_DAYS`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_URI`

## Endpoint unico

- `GET /fit/me`

Parametros opcionales:

- `start` (ISO datetime)
- `end` (ISO datetime)
- `bucket_days` (default 1)

Ejemplo:

GET `http://localhost:8000/fit/me?start=2026-05-01T00:00:00Z&end=2026-05-31T23:59:59Z`

Headers:

- `X-Google-Token: <access_token>`

Respuesta (resumen):

```json
{
  "user_id": "1234567890",
  "scopes": [
    "https://www.googleapis.com/auth/fitness.sleep.write",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.write",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.read",
    "https://www.googleapis.com/auth/fitness.nutrition.write",
    "https://www.googleapis.com/auth/fitness.nutrition.read",
    "https://www.googleapis.com/auth/fitness.location.write",
    "https://www.googleapis.com/auth/fitness.location.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.write",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.body.write",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.body_temperature.write",
    "https://www.googleapis.com/auth/fitness.body_temperature.read",
    "https://www.googleapis.com/auth/fitness.blood_pressure.write",
    "https://www.googleapis.com/auth/fitness.blood_pressure.read",
    "https://www.googleapis.com/auth/fitness.blood_glucose.write",
    "https://www.googleapis.com/auth/fitness.blood_glucose.read",
    "https://www.googleapis.com/auth/fitness.activity.write",
    "https://www.googleapis.com/auth/fitness.activity.read"
  ],
  "time_range": {
    "start_time": "2026-05-01T00:00:00+00:00",
    "end_time": "2026-05-31T23:59:59+00:00",
    "startTimeMillis": 1777593600000,
    "endTimeMillis": 1780271999000
  },
  "metrics": [
    {"name": "steps", "dataTypeName": "com.google.step_count.delta", "total": 12345}
  ],
  "sessions": [],
  "data_sources": []
}
```

## Ejecutar el Google Fit Service

Dev:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up --build googlefit_service
```

Prod:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build -d googlefit_service
```
