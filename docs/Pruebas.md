# Pruebas y evidencias

Este documento describe pasos reproducibles para validar funcionalidades clave y dónde recoger evidencias (logs, respuestas HTTP, tablas en Postgres).

## Preparación

1. Levantar el stack:

```bash
docker compose up --build
```

2. Verificar health del gateway:

```bash
curl http://localhost:8000/health
```

3. Obtener access token de `auth_service` (ejemplo):

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"moises@correo.com","password":"123456"}'
```

## Prueba: crear tarea y sincronizar con Google Calendar

1. Consigue un `X-Google-Token` válido (desde `google_auth` o consola Google OAuth playground).
2. Crear tarea con headers `Authorization` y `X-Google-Token`:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer <jwt>" \
  -H "X-Google-Token: <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"titulo":"Revisar informe","descripcion":"Pendiente de hoy","due_at":"2026-05-17T18:30:00Z"}'
```

3. Evidencias:
  - Respuesta HTTP 200/201 con `id_tarea`.
  - Log en `calendar_service` indicando intento de creación en Google.
  - Evento creado en el calendario asociado al `X-Google-Token`.

## Prueba: notificaciones por eventos

1. Crear tarea que dispare `Task.DueWarning` o `Task.Due` (usar `due_at` apropiado).
2. Verificar que `notifications_service` recibe evento y crea fila en su tabla `notifications`.
3. Evidencias: consulta en la DB `SELECT * FROM notifications WHERE id_usuario = '<id>'` o revisar logs con `docker compose logs notifications_service`.

## Prueba: Google Calendar endpoints directos

Ejecutar `GET /google/calendars` con `X-Google-Token` y verificar listado de calendarios.

```bash
curl -H "X-Google-Token: <token>" http://localhost:8000/google/calendars
```

## Logs y DB

- Logs de cada servicio: `docker compose logs <service_name>`.
- Consultas a Postgres: utilizar `psql` dentro del contenedor correspondiente o exponer puerto en `docker-compose` en desarrollo.

## Registro de evidencias

- Guarda respuestas HTTP (JSON) y capturas de pantalla o exporta logs a ficheros para auditoría.
**Pruebas — Auth y Google Auth**

Este documento recoge los ejemplos de petición (JSON) y descripción para los endpoints de `auth` y `google_auth`/`calendar_service` utilizados en el proyecto.

**Nota sobre las capturas:** Las capturas originales fueron provistas por el autor. Por seguridad se han retirado tokens y datos personales del contenido mostrado aquí. Si quieres incluir las imágenes en el repo, súbelas a `docs/images/` y reemplaza los marcadores de imagen por los nombres de fichero.

**Cabeceras comunes**
- **Authorization (JWT interno):** `Authorization: Bearer <JWT_INTERNO>`
- **Google token (acceso):** `X-Google-Token: <ACCESS_TOKEN_GOOGLE>`
- **Google refresh (opcional):** `X-Google-Refresh: <REFRESH_TOKEN_GOOGLE>`

---

**1) GET /auth/google/me**
- Descripción: Devuelve información básica del usuario autenticado con Google (provider: google, user, etc.).
- Headers: `Authorization: Bearer <ACCESS_TOKEN_GOOGLE>` (o `X-Google-Token`).
- Respuesta (ejemplo sanitizado):

```json
{
  "provider": "google",
  "user": {
    "email": "usuario@example.com",
    "name": "Nombre Ejemplo",
    "picture": "https://lh3.googleusercontent.com/....",
    "google_id": "1180952524270109074326",
    "email_verified": true
  }
}
```

Curl de ejemplo:

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN_GOOGLE>" \
  http://localhost:8000/auth/google/me
```

---

**2) POST /auth/google/refresh**
- Descripción: Intercambia un `refresh_token` de Google por un nuevo `access_token` (vía el flujo del microservicio `google_auth`).
- Body JSON: `refresh_token` (obligatorio).
- Respuesta (ejemplo sanitizado):

```json
{
  "provider": "google",
  "tokens": {
    "access_token": "<REDACTED_ACCESS_TOKEN>",
    "token_type": "Bearer",
    "expires_in": 3599,
    "refresh_token": "<REDACTED_REFRESH_TOKEN>",
    "scope": "...",
    "id_token": "<REDACTED_ID_TOKEN>"
  }
}
```

Curl de ejemplo:

```bash
curl -X POST http://localhost:8000/auth/google/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<REDACTED_REFRESH_TOKEN>"}'
```

---

**3) POST /auth/register**
- Descripción: Registra un usuario en el `auth_service` (no es Google).
- Body JSON (ejemplo):

```json
{
  "nombre": "Moisés Rodríguez",
  "email": "usuario@example.com",
  "password": "123456"
}
```

Respuesta esperada: `201 Created` con `id_usuario`, `nombre`, `email`, `created_at`.

---

**4) POST /auth/login**
- Descripción: Inicia sesión y devuelve `access_token` y `refresh_token` del `auth_service`.
- Body JSON (ejemplo):

```json
{
  "email": "usuario@example.com",
  "password": "123456"
}
```

Respuesta: JSON con `access_token`, `token_type`, `expires_in`, `refresh_token`, `refresh_expires_in`.

Curl de ejemplo:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"usuario@example.com","password":"123456"}'
```

---

**5) GET /auth/verify**
- Descripción: Valida internamente un JWT (proxy hacia `auth_service`).
- Headers: `Authorization: Bearer <JWT_INTERNO>`

Respuesta (ejemplo):

```json
{
  "valid": true,
  "id_usuario": "d1e9cc0f-c7e3-424d-92ac-85d77dc396d0",
  "email": "usuario@example.com"
}
```

---

**6) Endpoints de Google Calendar (via `calendar_service`)**

- Todos los endpoints de `google` requieren login con Google: usar `X-Google-Token` o `Authorization: Bearer <access_token_google>` y respetar `require_google_login` cuando corresponde.

6.1) POST /google/events — Crear evento

Body (CreateEventRequest):

```json
{
  "calendar_id": "primary",
  "summary": "Reunión con el equipo",
  "description": "Revisión de avances",
  "location": "Sala 3",
  "start": {"dateTime": "2026-05-16T15:00:00-05:00", "timeZone": "America/Lima"},
  "end": {"dateTime": "2026-05-16T16:00:00-05:00", "timeZone": "America/Lima"},
  "attendees": [{"email":"persona1@example.com","displayName":"Persona 1"}],
  "reminders": [{"method":"email","minutes":30},{"method":"popup","minutes":10}],
  "send_updates": "all"
}
```

Curl de ejemplo:

```bash
curl -X POST http://localhost:8000/google/events \
  -H "Content-Type: application/json" \
  -H "X-Google-Token: <ACCESS_TOKEN_GOOGLE>" \
  -d '{...JSON above...}'
```

6.2) PUT /google/events/{event_id} — Actualizar evento

- Body (UpdateEventRequest): mismos campos que Create but optional. Si no hay campos válidos, el backend responde 400.

Ejemplo sanitizado:

```json
{
  "calendar_id": "primary",
  "summary": "Reunión editada",
  "start": {"dateTime": "2026-05-16T15:30:00-05:00", "timeZone": "America/Lima"},
  "end": {"dateTime": "2026-05-16T16:30:00-05:00", "timeZone": "America/Lima"},
  "send_updates": "all"
}
```

Curl:

```bash
curl -X PUT http://localhost:8000/google/events/<EVENT_ID> \
  -H "Content-Type: application/json" \
  -H "X-Google-Token: <ACCESS_TOKEN_GOOGLE>" \
  -d '{...JSON above...}'
```

6.3) DELETE /google/events/{event_id} — Borrar evento

- No lleva body. Parámetro opcional `calendar_id` por query (por defecto `primary`).

Ejemplo:

```bash
curl -X DELETE "http://localhost:8000/google/events/<EVENT_ID>?calendar_id=primary" \
  -H "X-Google-Token: <ACCESS_TOKEN_GOOGLE>"
```

6.4) POST /google/refresh — Refrescar access token (calendar_service)

Body:

```json
{
  "refresh_token": "<REDACTED_REFRESH_TOKEN>",
  "access_token": null
}
```

Respuesta: `GoogleRefreshResponse` con nuevo `tokens` (ver ejemplos arriba).

Curl:

```bash
curl -X POST http://localhost:8000/google/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<REDACTED_REFRESH_TOKEN>"}'
```

---

**Incluir imágenes**
- Si quieres que las capturas se muestren en este `pruebas.md`, súbelas a `docs/images/` y añade líneas como:

```markdown
![auth-me](images/auth-me.png)
```

Recomendación: no incluyas tokens reales ni emails personales en el repo. Usa valores de ejemplo o redacta los valores sensibles.

---

Archivo generado: `docs/pruebas.md`

---

**7) Thunder Client - Task Service**

Base URL del gateway:

```text
http://localhost:8000
```

7.1) GET /tasks

- Descripción: lista las tareas del usuario autenticado.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Link:

```text
http://localhost:8000/tasks
```

7.2) POST /tasks

- Descripción: crea una tarea y, si mandas `X-Google-Token`, intenta publicar la sincronización con Google Calendar.
- Headers obligatorios: `Authorization: Bearer <JWT_INTERNO>`
- Headers opcionales: `X-Google-Token: <ACCESS_TOKEN_GOOGLE>`, `X-Google-Refresh: <REFRESH_TOKEN_GOOGLE>`

Body:

```json
{
  "titulo": "Revisar informe",
  "descripcion": "Pendiente de hoy",
  "due_at": "2026-05-17T18:30:00Z",
  "request_id": "d2d7f2c2-4c79-4c88-a0b5-7a7e3f1f6a11"
}
```

Link:

```text
http://localhost:8000/tasks
```

7.3) PATCH /tasks/{id_tarea}

- Descripción: marca la tarea como completada o actualiza `due_at`.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Body:

```json
{
  "completada": true,
  "due_at": "2026-05-17T19:00:00Z"
}
```

Link:

```text
http://localhost:8000/tasks/<ID_TAREA>
```

7.4) DELETE /tasks/{id_tarea}

- Descripción: elimina la tarea y publica el evento de descarte.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Link:

```text
http://localhost:8000/tasks/<ID_TAREA>
```

---

**8) Thunder Client - Notifications Service**

Base URL del gateway:

```text
http://localhost:8000
```

8.1) GET /notificaciones (ruta principal)

- Descripción: lista notificaciones del usuario autenticado.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Link:

```text
http://localhost:8000/notificaciones
```

Alias válido:

```text
http://localhost:8000/notifications
```

8.2) POST /notificaciones (ruta principal)

- Descripción: crea una notificación manual para el usuario autenticado.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Body:

```json
{
  "titulo": "Tarea vencida",
  "mensaje": "Tu tarea se venció hace 15 minutos",
  "tipo": "warning",
  "request_id": "8c873f56-4d20-4f73-8cf0-0f96bce0b4b2"
}
```

Link:

```text
http://localhost:8000/notificaciones
```

Alias válido:

```text
http://localhost:8000/notifications
```

8.3) PATCH /notificaciones/{notificacion_id}/leer (ruta principal)

- Descripción: marca una notificación como leída.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Link:

```text
http://localhost:8000/notificaciones/<ID_NOTIFICACION>/leer
```

Alias válido:

```text
http://localhost:8000/notifications/<ID_NOTIFICACION>/read
```

Alias adicional:

```text
http://localhost:8000/notifications/<ID_NOTIFICACION>/leer
```

8.4) PATCH /notificaciones/leer-todas (ruta principal)

- Descripción: marca todas las notificaciones del usuario como leídas.
- Header obligatorio: `Authorization: Bearer <JWT_INTERNO>`

Link:

```text
http://localhost:8000/notificaciones/leer-todas
```

Alias válido:

```text
http://localhost:8000/notifications/read-all
```

Alias adicional:

```text
http://localhost:8000/notifications/leer-todas
```

Nota: `POST /notificaciones/interna` existe en `notifications_service`, pero no está expuesto como ruta dedicada en el gateway principal.

---

**9) Thunder Client - Activity Service**

Base URL del gateway:

```text
http://localhost:8000
```

9.1) POST /activity/friends/request

- Descripcion: el usuario autenticado envia una solicitud de amistad a otro usuario.
- Header obligatorio: `Authorization: Bearer <JWT_USUARIO_1>`

Body:

```json
{
  "addressee_id": "<ID_USUARIO_2>"
}
```

Link:

```text
http://localhost:8000/activity/friends/request
```

Resultado esperado: `200 OK` con `requester_id` igual al usuario 1, `addressee_id` igual al usuario 2 y `status: "pending"`.

Evidencia requerida: captura de Thunder Client guardada como `docs/img/mandar_solicitud.png`.

![Mandar solicitud](img/mandar_solicitud.png)

9.2) GET /activity/friends

- Descripcion: lista las solicitudes y amistades del usuario autenticado.
- Header obligatorio: `Authorization: Bearer <JWT_USUARIO_2>`

Link:

```text
http://localhost:8000/activity/friends
```

Resultado esperado: `200 OK` con la solicitud recibida por el usuario 2 en `status: "pending"`.

Evidencia requerida: captura de Thunder Client guardada como `docs/img/ver_solicitud.png`.

![Ver solicitud recibida](img/ver_solicitud.png)

9.3) POST /activity/friends/{friendship_id}/accept

- Descripcion: el usuario destinatario acepta la solicitud de amistad.
- Header obligatorio: `Authorization: Bearer <JWT_USUARIO_2>`
- Body: no requiere body.

Link:

```text
http://localhost:8000/activity/friends/<FRIENDSHIP_ID>/accept
```

Resultado esperado: `200 OK` con la relacion actualizada a `status: "accepted"`.

Evidencia requerida: captura de Thunder Client guardada como `docs/img/aceptar_solicitud.png`.

![Aceptar solicitud](img/aceptar_solicitud.png)

9.4) GET /activity/friends

- Descripcion: confirma que la amistad quedo aceptada.
- Header obligatorio: `Authorization: Bearer <JWT_USUARIO_1>` o `Authorization: Bearer <JWT_USUARIO_2>`

Link:

```text
http://localhost:8000/activity/friends
```

Resultado esperado: `200 OK` con la relacion en `status: "accepted"` visible para los usuarios involucrados.

Evidencia requerida: captura de Thunder Client guardada como `docs/img/ver_solicitud_aceptada.png`.

![Ver solicitud aceptada](img/ver_solicitud_aceptada.png)

Capturas requeridas para este flujo:

- `docs/img/mandar_solicitud.png`
- `docs/img/ver_solicitud.png`
- `docs/img/aceptar_solicitud.png`
- `docs/img/ver_solicitud_aceptada.png`

---

**Bodies rápidos para copiar en Thunder Client**

- `POST /tasks`

```json
{
  "titulo": "Comprar materiales",
  "descripcion": "Ir a la papelería",
  "due_at": "2026-05-17T20:00:00Z"
}
```

- `PATCH /tasks/{id_tarea}`

```json
{
  "completada": false
}
```

- `POST /notificaciones`

```json
{
  "titulo": "Nueva tarea",
  "mensaje": "Se creó una tarea correctamente",
  "tipo": "success"
}
```

- `PATCH /notificaciones/{notificacion_id}/leer` no requiere body.

- `PATCH /notificaciones/leer-todas` no requiere body.

# Pruebas

Este documento registra pruebas manuales para validar los flujos principales de Kairos.

## Levantar servicios

```bash
docker compose build
docker compose up
```

## Verificar servicios

```bash
curl http://localhost:8000/health/auth_service
curl http://localhost:8000/health/task_service
curl http://localhost:8000/health/schedule_service
curl http://localhost:8000/health/stats_service
curl http://localhost:8000/health/notifications_service
```

## Flujo de tareas

1. Crear una tarea.
2. Completar la tarea.
3. Verificar notificación automática por tarea completada (`Task.Completed`).
4. Verificar que `stats_service` actualice estadísticas.
5. Verificar notificación automática por tarea próxima a vencer (`Task.DueWarning`).
6. Verificar notificación automática por tarea vencida (`Task.Due`) creando una tarea con `due_at` en el pasado.
7. Verificar notificación automática de error (`Task.Error`) cuando haya fallo en procesamiento.

## Flujo de horarios

1. Crear un bloque de horario.
2. Actualizar el bloque a `completed`.
3. Verificar que se publique el evento `bloque.completado`.
4. Verificar que `stats_service` actualice estadísticas.
5. Verificar que `notifications_service` cree una notificación.

### Evidencia en Thunder Client

#### Ver horarios

```http
GET http://localhost:8000/schedule
```

Resultado esperado: `200 OK`.

![GET schedule](img/schedule_get.png)

#### Crear horario

```http
POST http://localhost:8000/schedule
```

Resultado esperado: `200 OK` y respuesta con el `id` del bloque creado.

![POST schedule](img/schedule_post.png)

#### Modificar horario

```http
PATCH http://localhost:8000/schedule/{id}
```

Resultado esperado: `200 OK` y respuesta con los datos actualizados.

![PATCH schedule](img/schedule_patch.png)

#### Eliminar horario

```http
DELETE http://localhost:8000/schedule/{id}
```

Resultado esperado: `200 OK` y mensaje `Bloque eliminado`.

![DELETE schedule](img/schedule_delete.png)



## Logs útiles

```bash
docker compose logs -f task_service
docker compose logs -f schedule_service
docker compose logs -f stats_service
docker compose logs -f notifications_service
docker compose logs -f rabbitmq
```

## Capturas

### Auth

![Login](img/login.png)

![Registro](img/register.png)

![Verify token](img/verifytoken.png)

![Me](img/me.png)

![Me con nuevo token](img/me-new-token.png)

![Auth refresh](img/auth-refresh.png)

![Google login callback](img/googlelogin-callback.png)

![Google me](img/google-me.png)

![Google refresh](img/google-refresh.png)

![Credencial verificada](img/verify-credential.png)

![Token expirado](img/expired-token.png)

### Google Calendar

![Listar calendarios](img/get-google-calendar.png)

![Listar eventos](img/get-google-events.png)

![Crear evento Google](img/post-google-events.png)

![Modificar evento Google](img/modify-google-event.png)

![Eliminar evento Google](img/delete-google-event.png)

### Tasks

![Crear task](img/crear-task.png)

![Actualizar task](img/update-task.png)

![Leer tasks](img/read-tasks.png)

### Notifications

![Leer notification](img/read-notification.png)

![Leer notifications](img/read-notifications.png)

### Schedule

![Schedule GET](img/schedule_get.png)

![Schedule POST](img/schedule_post.png)

![Schedule PATCH](img/schedule_patch.png)

![Schedule DELETE](img/schedule_delete.png)

### Otros

![Eventos procesados](img/eventos%20procesados.png)

![Imagen](img/image.png)
