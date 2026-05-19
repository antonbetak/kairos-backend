# API — Endpoints principales

Este documento resume los endpoints más importantes del gateway con ejemplos de uso.

Todos los endpoints del gateway se acceden contra `http://localhost:8000`.

## Autenticación

- `POST /auth/register` — registra un usuario. Body: `{ "nombre": "", "email": "", "password": ""}`
- `POST /auth/login` — obtiene `access_token` y `refresh_token`. Body: `{ "email": "", "password": "" }`
- `POST /auth/refresh` — renueva tokens. Body: `{ "refresh_token": "..." }`
- `GET /auth/me` — devuelve el usuario actual; requiere `Authorization: Bearer <jwt>`

## Google OAuth

- `GET /auth/google/login` — inicia el flujo OAuth.
- `GET /auth/google/callback` — callback de Google.
- `POST /auth/google/refresh` — renueva tokens Google.

### Respuesta unificada de Google Auth

Los endpoints `GET /auth/google/callback` y `POST /auth/google/clerk/session` devuelven:

```json
{
  "provider": "google",
  "user": {
    "email": "user@example.com",
    "name": "User Example",
    "picture": "https://...",
    "google_id": "google-sub",
    "email_verified": true
  },
  "kairos_user": {
    "id_usuario": "uuid",
    "nombre": "User Example",
    "email": "user@example.com",
    "handle": "userexample",
    "avatar_url": "https://..."
  },
  "tokens": {
    "access_token": "google-access-token",
    "refresh_token": "google-refresh-token"
  },
  "kairos_tokens": {
    "access_token": "kairos-jwt",
    "refresh_token": "kairos-refresh-jwt"
  }
}
```

Internamente `google_auth` solicita la sincronizacion/creacion de usuario a `auth_service` por RabbitMQ (`auth.google.sync`).

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

- `GET /google/calendars` — lista calendars. El gateway puede inyectar el token de Google desde Clerk si la sesión del usuario es válida.
- `GET /google/events` — lista eventos del calendario.
- `POST /google/events` — crea evento en Google Calendar.
- `PUT /google/events/{id}`, `DELETE /google/events/{id}` — actualizar / borrar evento.

## Notifications

- `GET /notificaciones` — lista notificaciones (JWT requerido).
- `POST /notificaciones` — crear notificación manual.
- `PATCH /notificaciones/{id}/leer` — marcar como leída.

## Headers relevantes

- `Authorization: Bearer <jwt>` — para rutas protegidas por `auth_service` o Clerk session según el endpoint.
- `X-Google-Token: <access_token>` — opcional; el gateway puede inyectar el token de Google internamente si el usuario está autenticado.

Para ejemplos de `curl` y secuencias completas ver: [docs/pruebas.md](docs/pruebas.md)
