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
3. Verificar que se publique el evento `tarea.completada`.
4. Verificar que `stats_service` actualice estadísticas.
5. Verificar que `notifications_service` cree una notificación.

## Flujo de horarios

1. Crear un bloque de horario.
2. Actualizar el bloque a `completed`.
3. Verificar que se publique el evento `bloque.completado`.
4. Verificar que `stats_service` actualice estadísticas.
5. Verificar que `notifications_service` cree una notificación.

## Logs útiles

```bash
docker compose logs -f task_service
docker compose logs -f schedule_service
docker compose logs -f stats_service
docker compose logs -f notifications_service
docker compose logs -f rabbitmq
```
