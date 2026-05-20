# Decisiones técnicas

Resumen: este documento recoge las decisiones arquitectónicas y de diseño más relevantes para el proyecto, su justificación y posibles alternativas. Está pensado para ayudar a nuevos colaboradores a entender por qué se eligieron ciertas soluciones.

Registro de decisiones relevantes tomadas durante el diseño e implementación del backend.

## 1. Comunicación por eventos (RabbitMQ)

Decisión: usar RabbitMQ como bus de eventos para desacoplar productores y consumidores.  
Razonamiento: facilita escalado independiente, tolerancia a fallos y despliegues independientes.

## 2. API Gateway único

Decisión: exponer un único gateway al host y mantener servicios internos en red privada.  
Razonamiento: centraliza CORS, auth y enrutamiento; reduce superficie expuesta.

## 3. Tokens Google vs JWT

Decisión: separar tokens de sesión (JWT emitido por `auth_service`) de tokens de recursos externos (`X-Google-Token`).

## 7. Integración con Clerk (nueva)

Decisión: soportar autenticación delegada por Clerk pero mantener control de la entidad de usuario en Kairos. Para ello:

- Se añade `POST /auth/clerk/sync` en el gateway como el flujo canónico para sincronizar/crear usuarios Kairos tras un login con Clerk. El gateway valida/decodifica el Clerk JWT y llama a `auth_service` para crear/actualizar el usuario.
- El endpoint `POST /auth/clerk/exchange` mantiene una política más restrictiva: solo permite intercambiar una sesión Clerk por tokens Kairos si el `clerk_id` ya existe en Kairos; no crea usuarios automáticamente.
- Los flujos de Google que terminan en `google_auth` pueden causar sincronización vía RabbitMQ (`auth.google.sync`) hacia `auth_service`; en ese caso el payload puede incluir `clerk_id` y `auth_service` preservará dicho `clerk_id` al crear/actualizar el usuario.

Razonamiento: separar la responsabilidad de autenticación (Clerk) de la de gestión de identidad/atributos de aplicación (Kairos). Evitar creación implícita de usuarios en rutas de proxy reduce superficie de ataque y evita usuarios parciales cuando llamadas a Calendar/Fit ocurren sin intención de registro.

## 4. Idempotencia y `request_id`

Decisión: permitir `request_id` opcional en creaciones para soportar reintentos idempotentes en productores.

## 5. Manejo de errores upstream

Decisión: gateway realiza passthrough del status/headers cuando actúa como proxy; servicios internos manejan errores y publican eventos de error cuando procede.

## 6. Versionado de eventos

Recomendación: agregar campo `event_version` en el envelope cuando se introduzcan cambios incompatibles en el contrato.

## 8. Por qué una arquitectura distribuida

Decisión: optar por una arquitectura de microservicios distribuida en lugar de una aplicación monolítica.

Razonamiento:

- Escalabilidad: cada servicio (p. ej. `task_service`, `activity_service`, `calendar_service`) puede escalar de forma independiente según su carga y patrones de uso.
- Tolerancia a fallos y aislamiento: fallos en un servicio no implican la caída completa del sistema; los consumidores pueden rehacerse cuando el productor vuelve.
- Despliegue independiente: equipos pueden desplegar y liberar mejoras en servicios individuales sin bloquear todo el producto.
- Especialización tecnológica y responsabilidad limitada: permite elegir bibliotecas y optimizaciones particulares por servicio (p. ej. caching intensivo en `stats_service`) y respetar el principio de responsabilidad única.
- Costos de evolución: facilita refactorizaciones y cambios de contrato acotados en servicios concretos, minimizando el riesgo de regresiones globales.

Trade-offs:

- Complejidad operativa: requiere orquestación, observabilidad y herramientas de CI/CD más maduras.
- Latencia: las llamadas distribuidas y la comunicación asíncrona pueden introducir latencia que debe mitigarse con caches y diseño de timeouts.
- Consistencia: se debe diseñar para consistencia eventual cuando sea aceptable y aplicar compensaciones cuando no lo sea.

Conclusión: la elección se basó en las necesidades del dominio (eventos de usuario que demandan escalado y desacoplamiento) y en el objetivo de permitir equipos independientes y despliegues ágiles.
