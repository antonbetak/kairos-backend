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

### Paso 3: Configurar la pantalla de consentimiento OAuth

1. Ve a **APIs y servicios > Pantalla de consentimiento OAuth**.
2. Selecciona "Externo" como tipo de usuario.
3. Haz clic en "CREAR".
4. Rellena los campos requeridos:
   - **Nombre de la aplicación**: tu nombre de app (ej. "Kairos Google Auth")
   - **Email de asistencia**: tu email
   - **Datos de contacto del desarrollador**: tu email
5. Haz clic en "GUARDAR Y CONTINUAR".
6. En la sección de "Permisos", haz clic en "AGREGAR O ELIMINAR PERMISOS".
7. En la caja de búsqueda, busca y selecciona estos permisos:
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`
8. Haz clic en "ACTUALIZAR".
9. Haz clic en "GUARDAR Y CONTINUAR".
10. En "Usuarios de prueba", puedes agregar tus cuentas de Google para probar (opcional).
11. Haz clic en "GUARDAR Y CONTINUAR".

### Paso 4: Crear credenciales OAuth2

#### 4.1 - Credencial para Backend (Web)

1. Ve a **APIs y servicios > Credenciales**.
2. Haz clic en "CREAR CREDENCIALES" en la barra superior.
3. Selecciona "ID de cliente OAuth".
4. Elige **Tipo de aplicación: Aplicación web**.
5. Asigna un nombre (ej. "Kairos Backend API").
6. Bajo **URI de redirección autorizados**, agrega:
   - Desarrollo: `http://localhost:8000/auth/google/callback`
   - Staging: `https://staging-api.tu-dominio.com/auth/google/callback`
   - Producción: `https://api.tu-dominio.com/auth/google/callback`
7. Haz clic en "CREAR".
8. Se mostrará una ventana modal con:
   - `ID de cliente` (GOOGLE_CLIENT_ID)
   - `Secreto de cliente` (GOOGLE_CLIENT_SECRET)
9. **Copia estos valores** — los necesitarás en las variables de entorno del backend.
10. Haz clic en "CERRAR".

#### 4.2 - Credencial para iOS (Expo/EAS)

1. Nuevamente en **Credenciales**, haz clic en "CREAR CREDENCIALES".
2. Selecciona "ID de cliente OAuth".
3. Elige **Tipo de aplicación: Aplicación de iOS**.
4. Asigna un nombre (ej. "Kairos Mobile iOS").
5. En **Bundle ID**, ingresa tu Bundle ID de Expo. Puedes encontrarlo en:
   - `app.json` (campo `ios.bundleIdentifier`)
   - Si no lo has configurado, usa: `com.yourcompany.kairos` (reemplaza `yourcompany` con tu nombre)
6. En **ID de equipo**, déjalo vacío (si no tienes Apple Developer Team ID).
7. Haz clic en "CREAR".
8. Copia el `ID de cliente` que se genera (para uso en la app móvil).

#### 4.3 - Credencial para Android (Expo/EAS)

1. Nuevamente en **Credenciales**, haz clic en "CREAR CREDENCIALES".
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


## Variables de entorno del Backend

Copia el archivo `.env.example` a `.env` (o `.env.dev` para desarrollo) y rellena los valores con las credenciales web obtenidas en el **Paso 4.1**:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
APP_NAME=google_auth_service
APP_ENV=development
APP_PORT=8000
APP_HOST=0.0.0.0
APP_LOG_LEVEL=INFO

# Origenes permitidos (coma-separados)
CORS_ORIGINS=http://localhost:3000
# Tambien puedes usar JSON:
# CORS_ORIGINS=["http://localhost:3000","http://localhost:19006"]

# Credenciales obtenidas de Google Cloud Console
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Endpoints de Google OAuth (estandar, no cambiar)
GOOGLE_AUTH_URI=https://accounts.google.com/o/oauth2/v2/auth
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_USERINFO_URI=https://openidconnect.googleapis.com/v1/userinfo
GOOGLE_SCOPE=openid email profile

# Duracion del state token (en segundos)
STATE_TTL_SECONDS=600
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

### Probar sin frontend (Thunder Client o Postman)

1. Crea un GET a `http://localhost:8000/health` y confirma `status: ok`.
2. Crea un GET a `http://localhost:8000/auth/google/login` con "Follow redirects" desactivado.
3. Copia el header `Location` y abre esa URL en el navegador para hacer login.
4. Cuando Google redirija a `/auth/google/callback?code=...&state=...`, copia la URL completa.
5. Pega esa URL en Thunder Client y envia el GET para ver el JSON final.
6. Para refrescar, envia un POST a `http://localhost:8000/auth/google/refresh` con body JSON: `{"refresh_token":"..."}`.


## Endpoints principales

- `GET /auth/google/login` — inicia el flujo, redirige a Google.
- `GET /auth/google/callback` — callback que devuelve JSON con `user` y `tokens`.
- `POST /auth/google/refresh` — refresca el `access_token` usando `refresh_token`.
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
