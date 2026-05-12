# API Gateway

El **API Gateway** es el unico punto de entrada expuesto. Todos los microservicios quedan en red interna.

- Base URL: `http://localhost:8000`
- Health del gateway: `GET /health`
- Ready del gateway: `GET /ready`

# Endpoints por microservicio (via gateway)

- `google_auth`: `/auth/google/login`, `/auth/google/callback`, `/auth/google/refresh`, `/auth/google/me`.
- `auth_service`: `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/verify`.
- `calendar_service`: `/google/calendars`, `/google/events` (GET/POST), `/google/events/{id}` (PUT/DELETE), `/google/refresh`, `/device/calendars` (GET/POST), `/device/events` (GET/POST).
- `googlefit_service`: `/fit/me`.
- `task_service`: `/tasks` (GET/POST).
- `schedule_service`: `/schedule` (GET/POST), `/schedule/{id}` (GET/PATCH/DELETE).
- `stt_service`: `/stt/*` (ej. `/stt/health`).
- `notifications_service`: `/notifications/*` (ej. `/notifications/health`).
- `stats_service`: `/stats/*` (ej. `/stats/health`).
- `agent_service`: `/agent/*` (ej. `/agent/health`).
- Healths via gateway: `/health/google_auth`, `/health/calendar`, `/health/fit`, `/health/auth_service`, `/health/schedule_service`, `/health/task_service`, `/health/stt_service`, `/health/notifications_service`, `/health/stats_service`, `/health/agent_service`.

Nota: `/tasks` y `/schedule/*` requieren `Authorization: Bearer <token>` emitido por `auth_service`.
Nota: `auth_service` y `google_auth` son servicios distintos; sus rutas no colisionan.

# Auditoria de ramas del API Gateway

## Mapa de conflictos

| Aspecto | Rama A (feature/api_gateway) | Rama B (feature/integracion-auth-task-schedule-gateway) | Decision propuesta |
| --- | --- | --- | --- |
| Rutas duplicadas | `/health`, `/ready`, `/health/{service}`, `/ready/{service}`, `/auth/google/*`, `/google/*`, `/device/*`, `/fit/*` | `/health`, `/tasks`, `/schedule`, `/schedule/{id}` | Mantener ambas familias de rutas; `/health`
| Middlewares | CORS configurable via `CORS_ORIGINS` | Sin CORS | Conservar CORS aplicar dependencia de auth solo en rutas protegidas |
| Puertos | Gateway expone `API_GATEWAY_PORT` y usa URLs por env | URLs hardcodeadas a `auth_service`, `schedule_service`, `task_service`; no config de puerto en gateway | Centralizar URLs y puertos en `config.py` |
| Naming conventions | `google_auth`, `calendar-service`, `googlefit_service` | `auth_service`, `schedule_service`, `task_service` | Estandarizar nombres internos en config (snake_case) y permitir override por env. |
| Manejo de errores | Proxy con `HTTP 502` si falla upstream; reenvia status/headers | `response.json()` sin validar status; auth devuelve `401` en dependencia | Mantener comportamiento por ruta para compatibilidad; documentar que tasks/schedule responden JSON directo. |
| Autenticacion | No valida tokens | Dependencia `obtener_usuario_actual` con `Authorization: Bearer` | Conservar auth en `/tasks` y `/schedule/*`; no exigir auth en rutas de Google. |
| Formato de respuesta | Passthrough completo (status, headers, body) | JSON directo (sin status upstream) | Mantener passthrough para rutas proxy; mantener JSON directo para tasks/schedule. |

## Inventario de servicios

- `google_auth` -> `/auth/google/*` -> `http://google_auth:8000`
- `calendar_service` -> `/google/*`, `/device/*` -> `http://calendar-service:8000`
- `googlefit_service` -> `/fit/*` -> `http://googlefit_service:8000`
- `auth_service` -> `/auth/*` -> `http://auth_service:8000`
- `task_service` -> `/tasks` -> `http://task_service:8000`
- `schedule_service` -> `/schedule`, `/schedule/{id}` -> `http://schedule_service:8000`
- `stt_service` -> `/stt/*` -> `http://stt_service:8000`
- `notifications_service` -> `/notifications/*` -> `http://notifications_service:8000`
- `stats_service` -> `/stats/*` -> `http://stats_service:8000`
- `agent_service` -> `/agent/*` -> `http://agent_service:8000`

# Como correr el proyecto

1. Copia variables de entorno base:

```bash
copy .env.example .env
```

2. Ajusta secretos y credenciales en `.env`.
3. Levanta los servicios con Docker:

```bash
docker compose up --build
```

4. Verifica el gateway:

```bash
curl http://localhost:8000/health
```

Solo el API Gateway expone puertos al host; el resto de servicios quedan en red interna.

Nota: `docker-compose.dev.yml` y `docker-compose.prod.yml` cubren el stack de Google (auth/calendar/fit). Para el stack completo usa `docker-compose.yml`.

## Networks en Docker Compose

No es estrictamente necesario definir `networks` cuando usas un solo archivo Compose, porque Docker crea una red por defecto. Aun asi, se recomienda declararla explicitamente por estas razones:

- Hace explicita la red interna (`kairos-network`) para todos los servicios.
- Permite controlar el driver (bridge) y mantener la misma red si luego divides el stack en varios archivos Compose.
- Evita cambios de nombre automaticos de red si cambias el nombre del proyecto.

Como funciona:

- Todos los servicios que comparten `kairos-network` pueden resolverse por nombre de servicio (por ejemplo `auth_service`, `schedule_service`).
- El trafico entre servicios se mantiene dentro de la red interna, mientras que solo los puertos publicados con `ports` quedan expuestos al host.

# Pruebas basicas por servicio

| Servicio | Comando | Observaciones |
| --- | --- | --- |
| API Gateway | `curl http://localhost:8000/health` | Punto de entrada unico. |
| Google Auth | `curl http://localhost:8000/health/google_auth` | Health via gateway. |
| Calendar | `curl http://localhost:8000/health/calendar` | Health via gateway. |
| Google Fit | `curl http://localhost:8000/health/fit` | Health via gateway. |
| Auth Service | `curl http://localhost:8000/health/auth_service` | Health via gateway. |
| Schedule Service | `curl http://localhost:8000/health/schedule_service` | Health via gateway. |
| Task Service | `curl http://localhost:8000/health/task_service` | Health via gateway. |
| STT Service | `curl http://localhost:8000/health/stt_service` | Health via gateway. |
| Notifications Service | `curl http://localhost:8000/health/notifications_service` | Health via gateway. |
| Stats Service | `curl http://localhost:8000/health/stats_service` | Health via gateway. |
| Agent Service | `curl http://localhost:8000/health/agent_service` | Health via gateway. |

# Google Auth Service

El microservicio `google_auth`, responsable únicamente del proceso de autenticación con Google (OAuth2 / OpenID Connect). No extrae ni persiste datos de Google Fit, Calendar u otros servicios.

## Responsabilidades del servicio

- Iniciar el flujo OAuth2 con Google (`/auth/google/login`).
- Recibir el callback de Google, intercambiar el código por tokens, validar el `id_token` y devolver datos básicos del usuario (`/auth/google/callback`).
- Exponer un healthcheck (`/health`).

## Estructura relevante

- `google_auth/app/main.py` — arranque de FastAPI, middleware CORS y registro de rutas.
- `google_auth/app/config.py` — configuración validada desde variables de entorno.
- `google_auth/app/routes/auth.py` — endpoints `/auth/google/login` y `/auth/google/callback`.
- `google_auth/app/routes/health.py` — endpoint `/health`.
- `google_auth/app/services/google_oauth.py` — lógica de OAuth, firma/validación de `state`, intercambio de código y validación de `id_token`.
- `google_auth/requirements.txt` — dependencias.
- `google_auth/Dockerfile` — imagen para producción.

## Cómo funciona 

1. Cliente solicita `GET /auth/google/login`.
2. El servicio genera un `state` firmado (HMAC) que incluye un `nonce` y redirige al endpoint de autorización de Google.
3. Google autentica al usuario y redirige a `GET /auth/google/callback?code=...&state=...`.
4. El servicio valida la firma y la vigencia del `state`, intercambia el `code` por tokens en el endpoint de tokens de Google.
5. Valida el `id_token` con la librería oficial (`google-auth`) y obtiene `userinfo` si es necesario.
6. Devuelve JSON con `user` básico (email, name, picture, google_id) y el conjunto de tokens recibidos.

## Configuración de Google Cloud Console

### Paso 1: Crear un proyecto en Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. En la barra superior, haz clic en el proyecto actual (o en "Seleccionar un proyecto").
3. Haz clic en "NUEVO PROYECTO".
4. Asigna un nombre (ej. "Kairos Backend", "Mi App") y elige una organización (opcional).
5. Haz clic en "CREAR".
6. Espera a que se cree el proyecto. Verás un mensaje "Creando proyecto..." y después se te redirigirá.

### Paso 2: Habilitar Google+ API (para OpenID Connect)

1. En Google Cloud Console, busca "Google+ API" o "OAuth Consent Screen" en la barra de búsqueda.
2. Accede a **APIs y servicios > Biblioteca**.
3. Busca "Google+ API" y haz clic en ella.
4. Haz clic en "HABILITAR".

1. Ve a **APIs y servicios > Pantalla de consentimiento OAuth**.
2. Selecciona "Externo" como tipo de usuario.
3. Haz clic en "CREAR".
   - **Nombre de la aplicación**: tu nombre de app (ej. "Kairos Google Auth")
   - **Email de asistencia**: tu email
6. En la sección de "Permisos", haz clic en "AGREGAR O ELIMINAR PERMISOS".
7. En la caja de búsqueda, busca y selecciona estos permisos:
   - `openid`

### Paso 4: Crear credenciales OAuth2

   - Desarrollo: `http://localhost:8000/auth/google/callback`
   - Staging: `https://staging-api.tu-dominio.com/auth/google/callback`
   - Producción: `https://api.tu-dominio.com/auth/google/callback`
7. Haz clic en "CREAR".
8. Se mostrará una ventana modal con:
   - `ID de cliente` (GOOGLE_CLIENT_ID)
   - `Secreto de cliente` (GOOGLE_CLIENT_SECRET)
9. **Copia estos valores** — los necesitarás en las variables de entorno del backend.
#### 4.2 - Credencial para iOS (Expo/EAS)

1. Nuevamente en **Credenciales**, haz clic en "CREAR CREDENCIALES".
2. Selecciona "ID de cliente OAuth".
3. Elige **Tipo de aplicación: Aplicación de iOS**.
4. Asigna un nombre (ej. "Kairos Mobile iOS").
   - Si no lo has configurado, usa: `com.yourcompany.kairos` (reemplaza `yourcompany` con tu nombre)
6. En **ID de equipo**, déjalo vacío (si no tienes Apple Developer Team ID).
7. Haz clic en "CREAR".
8. Copia el `ID de cliente` que se genera (para uso en la app móvil).

#### 4.3 - Credencial para Android (Expo/EAS)
2. Selecciona "ID de cliente OAuth".
3. Elige **Tipo de aplicación: Aplicación de Android**.
4. Asigna un nombre (ej. "Kairos Mobile Android").
5. En **Nombre del paquete**, ingresa tu package name de Android. Puedes encontrarlo en:
   - `app.json` (campo `android.package`)
   - Si no lo has configurado, usa: `com.yourcompany.kairos` (reemplaza `yourcompany` con tu nombre)
6. En **Huella digital del certificado SHA-1**, necesitas obtener la del certificado de Expo:
   - Ejecuta en terminal: `expo doctor --fix` o `eas build --local` para generar el certificado si aún no existe
   - Alterna: Usa `openssl` para extraerla de tu keystore (si tienes uno), o déjalo en blanco por ahora y actualiza luego
7. Haz clic en "CREAR".
8. Copia el `ID de cliente` que se genera (para uso en la app móvil).

### Paso 5: Configuración en app.json (Expo/EAS)

Para que EAS compile y distribuya la app móvil correctamente, configura en tu `app.json`:

```json
{
  "expo": {
    "name": "Kairos",
    "slug": "kairos",
    "scheme": "kairos",
    "version": "1.0.0",
    "ios": {
      "bundleIdentifier": "com.yourcompany.kairos",
      "supportsTabletMode": true
    },
    "android": {
      "package": "com.yourcompany.kairos",
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#ffffff"
      }
    },
    "plugins": [
      ["expo-google-app-auth"]
    ]
  }
}
```

**Nota**: Reemplaza `yourcompany` con tu nombre de compañía o un identificador único.

### Paso 6: Configuración en EAS (eas.json)

Crea o actualiza tu `eas.json` en la raíz del proyecto móvil:

```json
{
  "cli": {
    "version": ">= 5.4.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {
      "distribution": "store"
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your-email@icloud.com",
        "appleTeamId": "YOUR_TEAM_ID"
      }
    }
  }
}
```

### Paso 7: Descargar credenciales y guardarlas

1. En la página de **Credenciales**, busca todas tus credenciales OAuth2 creadas (Web, iOS, Android).
2. Para cada una:
   - Haz clic en el icono de descarga para descargar un JSON con la información (recomendado para resguardo).
   - **NO subas estos JSONs a Git** — guárdalos localmente de forma segura.
3. Anota los siguientes valores:
   - **Web**: `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` (para backend)
   - **iOS**: `GOOGLE_CLIENT_ID_IOS` (para app móvil)
   - **Android**: `GOOGLE_CLIENT_ID_ANDROID` (para app móvil)

## Integración desde la app móvil (Expo)

### Instalación de dependencias

En tu proyecto Expo/React Native, instala las librerías necesarias:

```bash
npx expo install expo-google-app-auth
npx expo install expo-web-browser
npx expo install @react-native-async-storage/async-storage
```


### Variables de entorno en la app móvil

Crea un `.env` en la raíz de tu proyecto Expo:

```env
EXPO_PUBLIC_GOOGLE_CLIENT_ID_ANDROID=your-android-client-id.apps.googleusercontent.com
EXPO_PUBLIC_GOOGLE_CLIENT_ID_IOS=your-ios-client-id.apps.googleusercontent.com
EXPO_PUBLIC_API_BASE_URL=https://api.tu-dominio.com
```

### Deploy con EAS CLI

1. Instala y configura EAS CLI:

```bash
npm install -g eas-cli
eas login
```

2. Crea un perfil de build (si no existe `eas.json`):

```bash
eas build:configure
```

3. Para compilar en desarrollo:

```bash
eas build --platform android --profile development
eas build --platform ios --profile development
```

4. Para compilar para producción (Play Store / App Store):

```bash
eas build --platform android --profile production
eas build --platform ios --profile production
```

5. Para submitir a las tiendas (requiere cuentas activas):

```bash
eas submit --platform android --latest
eas submit --platform ios --latest
```

## Ejecutar y probar

### Docker (desarrollo)

```bash
docker compose -f docker-compose.dev.yml up --build
```

Verifica con:

```bash
curl http://localhost:8000/health
```

###  Docker (producción)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

## Endpoints principales

- `GET /auth/google/login` — inicia el flujo, redirige a Google.
- `GET /auth/google/callback` — callback que devuelve JSON con `user` y `tokens`.
- `POST /auth/google/refresh` — refresca el `access_token` usando `refresh_token`.
- `GET /auth/google/me` — devuelve el perfil del usuario usando `access_token` o `id_token`.
- `GET /health` — healthcheck.
- `GET /` — información básica del servicio.


## Notas operativas

- El `state` se firma con `GOOGLE_CLIENT_SECRET` para evitar la necesidad de almacenamiento externo (stateless).
- No se emite un JWT interno ni se persisten usuarios en esta fase.
- Asegurar que los **Redirect URIs en Google Cloud Console coincidan exactamente** con `GOOGLE_REDIRECT_URI` en `.env`.

## Solución de problemas

- **Error "invalid_client"**: Verifica que `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` sean correctos.
- **Error "redirect_uri_mismatch"**: Asegúrate de que el Redirect URI en Google Cloud Console coincida exactamente con `GOOGLE_REDIRECT_URI` (incluyendo http/https y puerto).
- **Error al validar id_token**: Verifica que la hora del sistema sea correcta (puede afectar validaciones de tokens).
- **CORS error**: Revisa que `CORS_ORIGINS` incluya el origen desde el cual se hace la solicitud.

# Google Calendar Service

Este microservicio integra Google Calendar API para listar calendarios, leer eventos y crear/actualizar/eliminar eventos. Solo opera con tokens de Google obtenidos en `google_auth`.

## Google Cloud Console (Calendar API)

1. Ve a **APIs y servicios > Biblioteca**.
2. Busca **Google Calendar API** y pulsa **HABILITAR**.
3. En la pantalla de consentimiento, asegúrate de incluir el scope:
   - `https://www.googleapis.com/auth/calendar`


## Seguridad (JWT + Google Token)

Cada request requiere al menos **uno** de estos:

- `Authorization: Bearer <JWT>` (token interno)
- `X-Google-Token: <access_token>` (token de Google)

Para los endpoints de Google Calendar (`/google/*`) **se requiere** `X-Google-Token`.
Si no tienes JWT interno, omite `Authorization` y envia solo `X-Google-Token`.


Header opcional:

- `X-Google-Refresh: <refresh_token>` (si quieres refrescar)

El JWT debe tener:

- `sub` con el UUID del usuario
- `exp` válido

## Variables de entorno requeridas (Calendar Service)

- `JWT_SECRET`
- `JWT_ALGORITHM` (ej: `HS256`)
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_URI`
- `GOOGLE_SCOPE` (debe incluir `https://www.googleapis.com/auth/calendar`)

## Endpoints del Calendar Service

- `GET /google/calendars`
- `GET /google/events`
- `POST /google/events`
- `PUT /google/events/{id}`
- `DELETE /google/events/{id}`
- `POST /google/refresh`
- `GET /device/calendars`
- `POST /device/calendars`
- `GET /device/events`
- `POST /device/events`
- `GET /health`
- `GET /ready`


### Listar calendarios

GET `http://localhost:8000/google/calendars`

Headers:

- `Authorization: Bearer <JWT>` (opcional)
- `X-Google-Token: <access_token>` (obligatorio)

### Listar eventos

GET `http://localhost:8000/google/events?calendar_id=primary&time_min=2025-01-01T00:00:00Z&time_max=2025-12-31T23:59:59Z`

Headers:

- `Authorization: Bearer <JWT>` (opcional)
- `X-Google-Token: <access_token>` (obligatorio)

### Crear evento

POST `http://localhost:8000/google/events`

Headers:

- `Authorization: Bearer <JWT>` (opcional)
- `X-Google-Token: <access_token>` (obligatorio)

Body:

```json
{
  "calendar_id": "primary",
  "summary": "Reunión de prueba",
  "description": "Evento creado desde API",
  "location": "Zoom",
  "start": {"dateTime": "2026-05-10T15:00:00-06:00"},
  "end": {"dateTime": "2026-05-10T16:00:00-06:00"},
  "attendees": [{"email": "invitado@example.com"}],
  "reminders": [{"method": "popup", "minutes": 30}]
}
```

### Actualizar evento

PUT `http://localhost:8000/google/events/{event_id}`

Body (parcial):

```json
{
  "calendar_id": "primary",
  "summary": "Reunión actualizada"
}
```

### Eliminar evento

DELETE `http://localhost:8000/google/events/{event_id}?calendar_id=primary`

### Refrescar access_token

POST `http://localhost:8000/google/refresh`

Body:

```json
{
  "refresh_token": "<refresh_token>"
}

## Device Calendar 

La lectura/creacion de eventos locales se hace en el dispositivo con Expo .
El backend solo recibe la informacion para sincronizar y mantener aislamiento por usuario.

### Instalacion en app Expo

```bash
npx expo install expo-calendar
```




### Probar endpoints de dispositivo

1) Sincroniza calendarios locales:

POST `http://localhost:8000/device/calendars`

Headers:

- `Authorization: Bearer <JWT>`

Body:

```json
{
  "calendars": [
    {"id": "local-1", "title": "Personal", "source": "device"}
  ]
}
```

2) Leer calendarios sincronizados:

GET `http://localhost:8000/device/calendars`

Headers:

- `Authorization: Bearer <JWT>`

3) Crear evento local (client-side) y notificar al backend:

POST `http://localhost:8000/device/events`

Headers:

- `Authorization: Bearer <JWT>`

Body:

```json
{
  "calendar_id": "local-1",
  "title": "Evento local",
  "start_date": "2026-05-10T15:00:00-06:00",
  "end_date": "2026-05-10T16:00:00-06:00",
  "notes": "Creado desde Expo Calendar",
  "location": "Dispositivo"
}
```

4) Leer eventos sincronizados:

GET `http://localhost:8000/device/events?calendar_id=local-1`

Headers:

- `Authorization: Bearer <JWT>`
```

## Ejecutar el Calendar Service

Dev:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up --build calendar-service
```

Prod:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build -d calendar-service
```

# Google Fit Service

Microservicio independiente para consultar datos de Google Fit en una sola respuesta.

## Google Cloud Console (Fitness API)

1. Ve a **APIs y servicios > Biblioteca**.
2. Busca **Fitness API** y pulsa **HABILITAR**.
3. En la pantalla de consentimiento, agrega estos scopes (lectura y escritura):
  - `https://www.googleapis.com/auth/fitness.sleep.write`
  - `https://www.googleapis.com/auth/fitness.sleep.read`
  - `https://www.googleapis.com/auth/fitness.oxygen_saturation.write`
  - `https://www.googleapis.com/auth/fitness.oxygen_saturation.read`
  - `https://www.googleapis.com/auth/fitness.nutrition.write`
  - `https://www.googleapis.com/auth/fitness.nutrition.read`
  - `https://www.googleapis.com/auth/fitness.location.write`
  - `https://www.googleapis.com/auth/fitness.location.read`
  - `https://www.googleapis.com/auth/fitness.heart_rate.write`
  - `https://www.googleapis.com/auth/fitness.heart_rate.read`
  - `https://www.googleapis.com/auth/fitness.body.write`
  - `https://www.googleapis.com/auth/fitness.body.read`
  - `https://www.googleapis.com/auth/fitness.body_temperature.write`
  - `https://www.googleapis.com/auth/fitness.body_temperature.read`
  - `https://www.googleapis.com/auth/fitness.blood_pressure.write`
  - `https://www.googleapis.com/auth/fitness.blood_pressure.read`
  - `https://www.googleapis.com/auth/fitness.blood_glucose.write`
  - `https://www.googleapis.com/auth/fitness.blood_glucose.read`
  - `https://www.googleapis.com/auth/fitness.activity.write`
  - `https://www.googleapis.com/auth/fitness.activity.read`

**Nota**: El `google_auth` debe solicitar estos scopes en `GOOGLE_SCOPE` para que el token tenga permisos de Fit.

## Seguridad

El endpoint `/fit/me` requiere un **access_token de Google**.

Headers:

- `X-Google-Token: <access_token>`
- `X-Google-Refresh: <refresh_token>` (opcional)

## Variables de entorno (Google Fit)

- `GOOGLE_FIT_PORT`
- `GOOGLE_FIT_API_BASE`
- `GOOGLE_FIT_SCOPES` (usar scopes de lectura y escritura)
- `FIT_BUCKET_DAYS`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_TOKEN_URI`

## Endpoint unico

- `GET /fit/me`

Parametros opcionales:

- `start` (ISO datetime)
- `end` (ISO datetime)
- `bucket_days` (default 1)

Ejemplo:

GET `http://localhost:8000/fit/me?start=2026-05-01T00:00:00Z&end=2026-05-31T23:59:59Z`

Headers:

- `X-Google-Token: <access_token>`

Respuesta (resumen):

```json
{
  "user_id": "1234567890",
  "scopes": [
    "https://www.googleapis.com/auth/fitness.sleep.write",
    "https://www.googleapis.com/auth/fitness.sleep.read",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.write",
    "https://www.googleapis.com/auth/fitness.oxygen_saturation.read",
    "https://www.googleapis.com/auth/fitness.nutrition.write",
    "https://www.googleapis.com/auth/fitness.nutrition.read",
    "https://www.googleapis.com/auth/fitness.location.write",
    "https://www.googleapis.com/auth/fitness.location.read",
    "https://www.googleapis.com/auth/fitness.heart_rate.write",
    "https://www.googleapis.com/auth/fitness.heart_rate.read",
    "https://www.googleapis.com/auth/fitness.body.write",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.body_temperature.write",
    "https://www.googleapis.com/auth/fitness.body_temperature.read",
    "https://www.googleapis.com/auth/fitness.blood_pressure.write",
    "https://www.googleapis.com/auth/fitness.blood_pressure.read",
    "https://www.googleapis.com/auth/fitness.blood_glucose.write",
    "https://www.googleapis.com/auth/fitness.blood_glucose.read",
    "https://www.googleapis.com/auth/fitness.activity.write",
    "https://www.googleapis.com/auth/fitness.activity.read"
  ],
  "time_range": {
    "start_time": "2026-05-01T00:00:00+00:00",
    "end_time": "2026-05-31T23:59:59+00:00",
    "startTimeMillis": 1777593600000,
    "endTimeMillis": 1780271999000
  },
  "metrics": [
    {"name": "steps", "dataTypeName": "com.google.step_count.delta", "total": 12345}
  ],
  "sessions": [],
  "data_sources": []
}
```

## Ejecutar el Google Fit Service

Dev:

```bash
docker compose --env-file .env.dev -f docker-compose.yml -f docker-compose.dev.yml up --build googlefit_service
```

Prod:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build -d googlefit_service
```
