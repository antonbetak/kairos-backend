# Requerimientos

## Requerimientos funcionales

- Registrar usuarios y autenticarlos (email/password + JWT).
- Autenticación vía Google (OAuth2) para obtener `X-Google-Token` y sincronizar Calendar / Fit.
- CRUD de Tareas (`task_service`).
- CRUD de Horarios (`schedule_service`).
- Sincronización opcional con Google Calendar cuando se provee `X-Google-Token`.
- Publicación y consumo de eventos de dominio vía RabbitMQ (Task.Created, Task.Completed, etc.).
- Generación de notificaciones automáticas (`notifications_service`).

## Requerimientos no funcionales

- Alta disponibilidad con contenedores Docker (cada servicio en su propio contenedor).
- Comunicaciones internas seguras (red interna de Docker Compose).
- Trazabilidad básica de eventos para auditoría.
- Latencia razonable en operaciones síncronas (gateway proxy).

## Pre-requisitos de desarrollo

- Docker y Docker Compose
- Python 3.10+ (para desarrollo local sin Docker)
- make / task runner opcional

## Dependencias externas

- Google APIs (OAuth2, Calendar, Fitness)
- RabbitMQ
- PostgreSQL
- Redis (opcional según servicio)
