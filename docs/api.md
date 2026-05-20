# API — Endpoints principales

Resumen: este documento describe de forma completa los endpoints expuestos por el API Gateway, su propósito dentro del ecosistema de microservicios y ejemplos de uso para pruebas e integración. Para la visión general del proyecto consulta el `README.md` en la raíz del repositorio.

Este documento resume los endpoints más importantes del gateway con ejemplos de uso.

Todos los endpoints del gateway se acceden contra `http://localhost:8000`.

## Autenticación

- `POST /auth/register` — registra un usuario local (email/password). Body: `{ "nombre": "", "email": "", "password": ""}`
- `POST /auth/login` — obtiene `access_token` y `refresh_token` del `auth_service`. Body: `{ "email": "", "password": "" }`
- `POST /auth/refresh` — renueva tokens. Body: `{ "refresh_token": "..." }`
- `GET /auth/me` — devuelve el usuario actual; requiere `Authorization: Bearer <jwt>`

### Clerk (login via Clerk)

- `POST /auth/clerk/sync` — endpoint en el gateway para sincronizar/crear un usuario Kairos tras un login con Clerk. Debe recibir `Authorization: Bearer <CLERK_SESSION_JWT>` (token de Clerk). El gateway valida/decodifica el token, construye el perfil y llama internamente a `auth_service` para crear/actualizar el usuario y emitir tokens Kairos. Respuesta: `kairos_user` y `kairos_tokens`.
- `POST /auth/clerk/exchange` — intercambio de sesión Clerk por tokens Kairos **solo si** `clerk_id` ya existe en Kairos (comportamiento restringido a evitar creación automática en este endpoint).

## Google OAuth y sincronización

- `GET /auth/google/login` — inicia el flujo OAuth (frontend).
- `GET /auth/google/callback` — callback de Google (handled by `google_auth`).
- `POST /auth/google/refresh` — renueva tokens Google.

Nota: los flujos de Google que terminan en `google_auth` pueden pedir a `auth_service` (vía RabbitMQ) la creación/sincronización del usuario Kairos; en ese flujo se puede incluir `clerk_id` para que el usuario quede asociado a la cuenta de Clerk.

### Respuesta unificada de Google Auth (ejemplo)

```json
{
  "provider": "google",
  "user": { "email": "user@example.com", "name": "User Example", "picture": "https://...", "google_id": "google-sub", "email_verified": true },
  "kairos_user": { "id_usuario": "uuid", "nombre": "User Example", "email": "user@example.com", "handle": "userexample", "avatar_url": "https://..." },
  "tokens": { "access_token": "google-access-token", "refresh_token": "google-refresh-token" },
  "kairos_tokens": { "access_token": "kairos-jwt", "refresh_token": "kairos-refresh-jwt" }
}
```

Internamente `google_auth` solicita la sincronización/creación de usuario a `auth_service` por RabbitMQ (`auth.google.sync`). El consumidor en `auth_service` ahora preserva `clerk_id` si se incluye en el payload.

## Tasks

- `GET /tasks` — lista tareas del usuario (JWT requerido).
- `POST /tasks` — crea tarea. Ejemplo body:

```json
{
  "titulo": "Revisar informe",
  "descripcion": "Pendiente de hoy",
  "due_at": "2026-05-17T18:30:00Z",
  "request_id": "uuid-opcional"
}
```

- `PATCH /tasks/{id}` — actualiza campos (`completada`, `due_at`, ...).
- `DELETE /tasks/{id}` — elimina tarea.

## Schedule

- `GET /schedule` — lista bloques del usuario.
- `POST /schedule` — crea un bloque. Body similar a `modelo-datos`.
- `PATCH /schedule/{id}` — actualiza bloque.
- `DELETE /schedule/{id}` — elimina bloque.

## Google Calendar proxy

- `GET /google/calendars` — lista calendars. El gateway puede inyectar el token de Google desde Clerk si la sesión del usuario es válida; **NO** crea usuarios Kairos automáticamente cuando se llama a rutas de Calendar/Fit.
- `GET /google/events` — lista eventos del calendario.
- `POST /google/events` — crea evento en Google Calendar.
- `PUT /google/events/{id}`, `DELETE /google/events/{id}` — actualizar / borrar evento.

## Notifications

- `GET /notificaciones` — lista notificaciones (JWT requerido).
- `POST /notificaciones` — crear notificación manual.
- `PATCH /notificaciones/{id}/leer` — marcar como leída.

## Activity

- `GET /activity/me` — información de actividad del usuario autenticado (resumen).
- `GET /activity/feed` — feed de actividad del usuario (paginado). Requiere `Authorization: Bearer <jwt>`.
- `GET /activity/events` — lista eventos de actividad (filterable por tipo/usuario).
- `POST /activity/events` — crear un evento de actividad manual (uso interno / testing). Body ejemplo:

```json
{
  "tipo": "task.completed",
  "id_usuario": "uuid",
  "titulo": "Completó: Reunión semanal",
  "meta": { "id_tarea": "uuid" }
}
```

- `POST /activity/events/{id}/react` — agregar reacción a un evento (body: `{ "tipo": "like" }`).
- `POST /activity/events/{id}/comments` — agregar comentario a un evento (body: `{ "texto": "Buen trabajo" }`).
- `GET /activity/friends` — lista de amigos / conexiones.
- `POST /activity/friends/request` — enviar solicitud de amistad (body: `{ "to_user_id": "uuid" }`).
- `POST /activity/friends/{id}/accept` — aceptar solicitud de amistad.
- `GET /activity/invites` — lista invitaciones recibidas.

## Headers relevantes

- `Authorization: Bearer <jwt>` — para rutas protegidas por `auth_service` o para enviar un `Clerk` session JWT al endpoint `POST /auth/clerk/sync`.
- `X-Google-Token: <access_token>` — opcional; el gateway puede inyectar el token de Google internamente si el usuario está autenticado y tiene token disponible en Clerk.
- `X-Internal-Token: <secret>` — token interno usado por el gateway para llamar a APIs privadas de `auth_service` (configurado en despliegue).

Para ejemplos de `curl` y secuencias completas ver: [docs/Pruebas.md](Pruebas.md)
