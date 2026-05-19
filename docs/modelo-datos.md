# Modelo de datos (resumen)

Este documento describe las entidades principales y sus campos más relevantes. No sustituye el esquema de la base de datos en cada servicio, sino que ofrece una visión global.

## Usuario (`users` / `auth_service`)

- `id_usuario` (UUID)
- `nombre` (string)
- `email` (string, único)
- `password_hash` (string)
- `created_at`, `updated_at` (timestamps)

## Tarea (`tasks` / `task_service`)

- `id_tarea` (UUID)
- `request_id` (UUID) — opcional, correlación de solicitudes / origen externo
- `id_usuario` (UUID)
- `titulo` (string)
- `descripcion` (text)
- `completada` (bool)
- `due_at` (timestamp, nullable)
- `due_warning_sent_at` (timestamp, nullable)
- `created_at`, `updated_at` (timestamps)

## Horario / Bloque (`schedules` / `schedule_service`)

- `id` (UUID)
- `id_usuario` (UUID)
- `titulo`, `descripcion` (strings)
- `fecha_inicio`, `fecha_fin` (timestamps)
- `tipo` (enum: study, work, meeting...)
- `status` (planned, completed, cancelled)
- `created_at`, `updated_at`

## Notificación (`notifications` / `notifications_service`)

- `id_notificacion` (UUID)
- `id_usuario` (UUID)
- `titulo`, `mensaje` (strings)
- `tipo` (recordatorio, logro, error, cumplimiento)
- `leida` (bool)
- `fecha_creacion`, `fecha_lectura` (timestamps)

## Sincronización con Google (calendar_service)

Cuando se crea un `Task` o `Schedule` con un `X-Google-Token`, `calendar_service` genera un evento con los campos básicos:

- `summary` <- `titulo`
- `description` <- `descripcion`
- `start.dateTime` / `end.dateTime` <- `due_at` o `fecha_inicio`/`fecha_fin`
- `attendees`, `reminders` (opcional)

Para detalles completos consultar: [docs/modelo-datos.md] (documentación por servicio).
