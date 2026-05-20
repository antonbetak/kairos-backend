## auth.google.sync (síncrona via RPC / petición)

Cuando `google_auth` solicita la creación/sincronización de un usuario en `auth_service` puede enviar un payload que incluya `clerk_id` (si el usuario proviene de Clerk). Ejemplo mínimo:

```json
{
  "action": "google.sync_user",
  "data": {
    "email": "user@example.com",
    "nombre": "User Example",
    "google_id": "1180952524270109074326",
    "avatar_url": "https://...",
    "clerk_id": "clerk_abc123"   
  }
}
```

`auth_service` preserva `clerk_id` en la cuenta creada/actualizada cuando se provee.
# Eventos (contratos)

Resumen: contratos de eventos (payloads y ejemplos) que circulan por RabbitMQ y mecanismos RPC usados para sincronización entre servicios. Mantener estos contratos actualizados es crítico para evitar rupturas entre productores y consumidores.

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

## Activity Service — eventos y transformaciones

`activity_service` consume eventos de dominio (especialmente `Task.*`, `Schedule.*`, `logro.*`) y produce eventos de actividad pensados para mostrar en el feed del usuario o para exportar a servicios de analítica. Ejemplos:

- Consume: `Task.Created`, `Task.Completed`, `Task.Due`, `Schedule.Created`, `Schedule.Updated`.
- Produce: `Activity.EventCreated` (payload con resumen legible para UI), `Achievement.Unlocked`, `Streak.Updated`.

Ejemplo `Activity.EventCreated` payload:

```json
{
  "event_type": "Activity.EventCreated",
  "data": {
    "id": "uuid",
    "id_usuario": "uuid",
    "tipo": "task.completed",
    "titulo": "Completó: Revisar informe",
    "meta": { "id_tarea": "uuid", "puntos": 10 },
    "created_at": "2026-05-17T07:16:29Z"
  }
}
```

Notas:

- `activity_service` debe aplicar deduplicación y agregación temporal (p. ej. agrupar varias completaciones en un resumen diario) para evitar ruido en el feed.
- Los contratos de salida de `activity_service` son consumidos por UI y por `stats_service` para agregación adicional.
