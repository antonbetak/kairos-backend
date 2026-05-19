# Eventos (contratos)

Listamos los eventos principales que circulan por RabbitMQ y ejemplos de payload.

## Task.Created

Producer: `task_service`  
Consumers: `notifications_service`, `schedule_service`, `stats_service`, `calendar_service` (si hay `X-Google-Token`)

Ejemplo payload:

```json
{
  "event_id": "uuid",
  "event_type": "Task.Created",
  "data": {
    "id_tarea": "uuid",
    "id_usuario": "uuid",
    "titulo": "Revisar informe",
    "descripcion": "Pendiente de hoy",
    "due_at": "2026-05-17T18:30:00Z",
    "request_id": "uuid-opcional"
  },
  "created_at": "2026-05-17T07:16:29Z"
}
```

## Task.Completed

Producer: `task_service`  
Consumers: `notifications_service`, `stats_service`

Payload:

```json
{
  "event_type": "Task.Completed",
  "data": { "id_tarea": "uuid", "id_usuario": "uuid", "completed_at": "..." }
}
```

## Task.DueWarning / Task.Due

Producer: `task_service` (scheduler interno)

Payload similar a Task.Created con `event_type` distinto.

## Schedule.Created / Schedule.Updated

Producer: `schedule_service`  
Consumers: `notifications_service`, `stats_service`, `calendar_service`

Ejemplo:

```json
{
  "event_type": "Schedule.Created",
  "data": {
    "id": "uuid",
    "id_usuario": "uuid",
    "titulo": "Bloque de estudio",
    "fecha_inicio": "2026-05-16T18:30:00Z",
    "fecha_fin": "2026-05-16T20:00:00Z"
  }
}
```

## Notas sobre versiones y compatibilidad

- Incluir `event_version` en el envelope si se prevé evolucionar el contrato.
- Validar la presencia de campos esenciales (`id`, `id_usuario`) y manejar mensajes idempotentes por `event_id`/`request_id`.
