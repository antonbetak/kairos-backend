# Fallas simuladas

Resumen: escenarios documentados para probar la resiliencia del sistema (fallos en infra y en proveedores externos), pasos reproducibles y verificación de resultados.

Escenarios para probar resiliencia y tolerancia a fallos.

## 1. Caída de RabbitMQ

Objetivo: comprobar que los productores manejan reintentos y que los consumidores vuelven a procesar mensajes cuando RabbitMQ vuelve.

Cómo reproducir:

```bash
docker compose stop rabbitmq
# ejecutar operaciones que publiquen eventos (p. ej. crear tareas)
docker compose start rabbitmq
```

Verificar:
- Que no haya pérdida de eventos (o que existan reintentos configurados).
- Logs de `task_service` mostrando fallo al publicar y reintento.

## 2. Error en Google API (403/401)

Objetivo: comprobar manejo de errores y reintentos cuando Google devuelve errores (token expirado, permisos insuficientes).

Cómo reproducir:
- Usar un `X-Google-Token` inválido o revocado.
- Crear una tarea con `X-Google-Token` inválido.

Verificar:
- `calendar_service` captura error, registra evento `Schedule.Error` o similar.
- Notificaciones al usuario si está configurado.

## 3. Base de datos no disponible

Objetivo: verificar que el servicio responde correctamente (500) y que los writes no corruptos no ocurren.

Cómo reproducir:

```bash
docker compose stop postgres
# llamar endpoint que escribe en BD
docker compose start postgres
```

Verificar:
- El servicio debe retornar error controlado y logs con stacktrace.

## 4. Expiración de tokens JWT

Objetivo: validar que `auth_service` devuelve `401` y el flujo de refresh funciona correctamente.

Cómo reproducir:
- Forzar expiración del token (usar token con `exp` corto) o modificar `JWT_LEEWAY`.

Verificar:
- `GET /auth/me` con token expirado → `401`.  
- `POST /auth/refresh` con `refresh_token` válido → nuevos tokens.

## 5. Fallo en servicio de terceros: Clerk

Objetivo: comprobar el comportamiento cuando la verificación del token de Clerk o la llamada a la API de Clerk (para obtener `oauth_access_tokens/google`) falla.

Cómo reproducir:

```bash
# Simular JWKS no disponible o respuesta 500 desde Clerk
```

Verificar:
- El gateway debe responder 502/504 o un error claro y no crear usuarios Kairos automáticamente.
- Las llamadas a `POST /auth/clerk/sync` deben fallar de forma controlada si Clerk no puede verificarse.
- Los logs deben contener trazas para facilitar reintentos manuales.
