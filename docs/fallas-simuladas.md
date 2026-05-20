# Fallas simuladas

Este documento describe dos fallas simuladas para demostrar el manejo de errores del backend de Kairos.

Las pruebas se ejecutan con Docker Compose y el API Gateway en:

```text
http://localhost:8000
```

---

## 1. Falla simulada: base de datos no disponible

### Objetivo

Comprobar qué ocurre cuando un microservicio intenta leer o escribir información, pero su base de datos no está disponible temporalmente.

En esta prueba se usa `task_service`, porque depende de `task_postgres` para guardar y consultar tareas.

### Servicio afectado

- `task_service`
- `task_postgres`

### Pasos para simular la falla

1. Levantar el proyecto completo:

```bash
docker compose up --build
```

2. Verificar que el servicio de tareas funciona antes de la falla:

```bash
curl -X GET http://localhost:8000/tasks \
  -H "Authorization: Bearer <TOKEN>"
```

3. Detener únicamente la base de datos de tareas:

```bash
docker compose stop task_postgres
```

4. Intentar consultar o crear una tarea mientras la base de datos está detenida:

```bash
curl -X GET http://localhost:8000/tasks \
  -H "Authorization: Bearer <TOKEN>"
```

O bien:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "titulo": "Tarea con base de datos caída",
    "descripcion": "Prueba de falla simulada"
  }'
```

5. Revisar logs del servicio:

```bash
docker compose logs -f task_service
```

6. Restaurar la base de datos:

```bash
docker compose start task_postgres
```

7. Volver a consultar tareas:

```bash
curl -X GET http://localhost:8000/tasks \
  -H "Authorization: Bearer <TOKEN>"
```

### Resultado esperado

- Mientras `task_postgres` está detenido, `task_service` no puede completar la consulta o escritura.
- El gateway devuelve un error en vez de responder datos incompletos.
- En los logs aparece el error de conexión a la base de datos.
- Cuando `task_postgres` vuelve a iniciar, el servicio recupera su operación normal.
- No se crean registros corruptos o incompletos durante la falla.

### Evidencia sugerida

- Captura del comando `docker compose stop task_postgres`.
- Captura de Thunder Client o terminal mostrando error al llamar `/tasks`.
- Captura de logs de `task_service`.
- Captura posterior mostrando que `/tasks` vuelve a responder al reiniciar `task_postgres`.

---

## 2. Falla simulada: proceso queda pendiente

### Objetivo

Comprobar que el sistema evita ejecutar dos veces la misma operación cuando una solicitud queda marcada como en proceso.

El backend usa `request_id` e idempotencia para marcar operaciones como `PROCESSING`. Si se repite la misma operación antes de que termine o antes de que expire el bloqueo temporal, el servicio responde con conflicto.

En esta prueba se usa `schedule_service`, porque al crear bloques usa `request_id` y reserva idempotente.

### Servicio afectado

- `schedule_service`
- Redis, usado para guardar el estado temporal de idempotencia.

### Pasos para simular la falla

1. Levantar el proyecto completo:

```bash
docker compose up --build
```

2. Elegir un `request_id` fijo para repetir la misma operación:

```text
11111111-1111-4111-8111-111111111111
```

3. Enviar una solicitud para crear un bloque de horario con ese `request_id`:

```bash
curl -X POST http://localhost:8000/schedule \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "11111111-1111-4111-8111-111111111111",
    "titulo": "Bloque pendiente",
    "descripcion": "Prueba de proceso pendiente",
    "fecha_inicio": "2026-05-20T10:00:00",
    "fecha_fin": "2026-05-20T11:00:00",
    "tipo": "tarea",
    "status": "planned"
  }'
```

4. Simular que el proceso quedó pendiente escribiendo manualmente el estado `PROCESSING` en Redis con el mismo `request_id`:

```bash
docker compose exec redis redis-cli set idempotency:schedule:11111111-1111-4111-8111-111111111111 PROCESSING EX 60
```

5. Repetir inmediatamente la misma solicitud:

```bash
curl -X POST http://localhost:8000/schedule \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "11111111-1111-4111-8111-111111111111",
    "titulo": "Bloque pendiente",
    "descripcion": "Prueba de proceso pendiente",
    "fecha_inicio": "2026-05-20T10:00:00",
    "fecha_fin": "2026-05-20T11:00:00",
    "tipo": "tarea",
    "status": "planned"
  }'
```

6. Revisar logs del servicio:

```bash
docker compose logs -f schedule_service
```

7. Esperar a que expire el bloqueo temporal o eliminarlo manualmente:

```bash
docker compose exec redis redis-cli del idempotency:schedule:11111111-1111-4111-8111-111111111111
```

### Resultado esperado

- La segunda solicitud con el mismo `request_id` no debe crear otro bloque.
- El servicio responde con `409 Conflict`.
- El mensaje esperado es:

```json
{
  "detail": "El horario ya se está procesando"
}
```

- La operación queda protegida contra duplicados mientras el `request_id` está en estado `PROCESSING`.
- Al expirar o eliminar el bloqueo en Redis, el sistema puede volver a procesar solicitudes normalmente.

### Evidencia sugerida

- Captura del `request_id` usado.
- Captura del comando que escribe `PROCESSING` en Redis.
- Captura de la respuesta `409 Conflict`.
- Captura de logs de `schedule_service`.
