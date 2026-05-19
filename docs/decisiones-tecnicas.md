# Decisiones técnicas

Registro de decisiones relevantes tomadas durante el diseño e implementación del backend.

## 1. Comunicación por eventos (RabbitMQ)

Decisión: usar RabbitMQ como bus de eventos para desacoplar productores y consumidores.  
Razonamiento: facilita escalado independiente, tolerancia a fallos y despliegues independientes.

## 2. API Gateway único

Decisión: exponer un único gateway al host y mantener servicios internos en red privada.  
Razonamiento: centraliza CORS, auth y enrutamiento; reduce superficie expuesta.

## 3. Tokens Google vs JWT

Decisión: separar tokens de sesión (JWT emitido por `auth_service`) de tokens de recursos externos (`X-Google-Token`).

## 4. Idempotencia y `request_id`

Decisión: permitir `request_id` opcional en creaciones para soportar reintentos idempotentes en productores.

## 5. Manejo de errores upstream

Decisión: gateway realiza passthrough del status/headers cuando actúa como proxy; servicios internos manejan errores y publican eventos de error cuando procede.

## 6. Versionado de eventos

Recomendación: agregar campo `event_version` en el envelope cuando se introduzcan cambios incompatibles en el contrato.
