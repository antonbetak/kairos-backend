from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token

from app.config import Settings
from app.schemas import GoogleAuthResponse, GoogleTokenSet, GoogleUserProfile
from app.services.auth_sync_bus import AuthSyncBusClient


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StatePayload:
    nonce: str
    issued_at: int
    client_id: str
    redirect_uri: str


class GoogleOAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._state_secret = settings.google_client_secret.encode("utf-8")
        self._auth_sync_bus = AuthSyncBusClient(settings)

    async def _token_status(self, token: str) -> bool:
        url = f"{self.settings.auth_service_url.rstrip('/')}/auth/token-status"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json={"token": token})

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No fue posible validar el estado del token.",
            )

        return bool(response.json().get("blacklisted"))

    async def _blacklist_token(self, token: str) -> None:
        url = f"{self.settings.auth_service_url.rstrip('/')}/auth/token-blacklist"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json={"token": token})

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No fue posible invalidar el token anterior.",
            )

    def build_authorization_url(
        self,
        platform: str | None = None,
        redirect_uri: str | None = None,
    ) -> str:
        client_id, _ = self._resolve_client(platform)
        redirect_uri_value = self._resolve_redirect_uri(redirect_uri)
        state = self._create_state(
            client_id=client_id,
            redirect_uri=redirect_uri_value,
        )
        query = {
            "client_id": client_id,
            "redirect_uri": redirect_uri_value,
            "response_type": "code",
            "scope": self.settings.google_scope,
            "state": state,
            "nonce": self._extract_state_payload(state).nonce,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent select_account",
        }
        return f"{self.settings.google_auth_uri}?{urlencode(query)}"

    async def exchange_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
    ) -> dict[str, object]:
        payload = {
            "code": code,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        if self._should_use_client_secret(client_id):
            payload["client_secret"] = self.settings.google_client_secret

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self.settings.google_token_uri, data=payload)

        if response.status_code >= 400:
            logger.warning("Google token exchange failed: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible intercambiar el código de autorización con Google.",
            )

        return response.json()

    async def refresh_tokens(
        self,
        refresh_token: str,
        platform: str | None = None,
    ) -> GoogleTokenSet:
        if await self._token_status(refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El refresh token de Google fue invalidado.",
            )

        client_id, use_client_secret = self._resolve_client(platform)

        payload = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "grant_type": "refresh_token",
        }

        if use_client_secret:
            payload["client_secret"] = self.settings.google_client_secret

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self.settings.google_token_uri, data=payload)

        if response.status_code >= 400:
            logger.warning("Google token refresh failed: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible refrescar el access_token con Google.",
            )

        token_response = response.json()
        access_token = token_response.get("access_token")

        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google no devolvió un access_token válido.",
            )

        tokens = GoogleTokenSet(
            access_token=access_token,
            token_type=str(token_response.get("token_type") or "Bearer"),
            expires_in=token_response.get("expires_in"),
            refresh_token=str(token_response.get("refresh_token") or refresh_token),
            scope=str(token_response.get("scope") or self.settings.google_scope),
            id_token=token_response.get("id_token"),
        )

        return tokens

    def verify_id_token(
        self, token: str, expected_nonce: str | None = None
    ) -> dict[str, object]:
        request = Request()

        last_error: Exception | None = None
        for audience in self.settings.allowed_google_client_ids():
            try:
                claims = google_id_token.verify_oauth2_token(
                    token,
                    request,
                    audience=audience,
                    clock_skew_in_seconds=self.settings.clock_skew_seconds,
                )
                if expected_nonce and claims.get("nonce") != expected_nonce:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="El nonce del token no coincide con la autenticación iniciada.",
                    )

                return claims
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        logger.warning("Google id_token validation failed: %s", last_error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El id_token de Google no es válido.",
        ) from last_error

    async def get_current_user(self, token: str) -> GoogleUserProfile:
        if await self._token_status(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de Google fue invalidado.",
            )

        try:
            claims = self.verify_id_token(token)
            return self._build_user_profile(claims)
        except HTTPException:
            pass

        userinfo = await self.fetch_userinfo(token)
        if not userinfo:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token de Google no es válido.",
            )

        return self._build_user_profile(userinfo)

    async def fetch_userinfo(self, access_token: str) -> dict[str, object]:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                self.settings.google_userinfo_uri, headers=headers
            )

        if response.status_code >= 400:
            logger.warning("Google userinfo request failed: %s", response.text)
            return {}

        return response.json()

    async def authenticate(self, code: str, state: str) -> GoogleAuthResponse:
        state_payload = self._extract_state_payload(state)
        token_response = await self.exchange_code(
            code,
            client_id=state_payload.client_id,
            redirect_uri=state_payload.redirect_uri,
        )

        id_token_value = token_response.get("id_token")
        access_token = token_response.get("access_token")

        if not isinstance(id_token_value, str) or not id_token_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google no devolvió un id_token válido.",
            )

        if not isinstance(access_token, str) or not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google no devolvió un access_token válido.",
            )

        id_token_claims = self.verify_id_token(id_token_value, state_payload.nonce)
        userinfo = await self.fetch_userinfo(access_token)

        combined = dict(id_token_claims)
        combined.update(userinfo or {})
        user = self._build_user_profile(combined)

        tokens = GoogleTokenSet(
            access_token=access_token,
            token_type=str(token_response.get("token_type") or "Bearer"),
            expires_in=token_response.get("expires_in"),
            refresh_token=token_response.get("refresh_token"),
            scope=str(token_response.get("scope") or self.settings.google_scope),
            id_token=id_token_value,
        )

        logger.info(
            "Google OAuth authenticate: user=%s google_access_token=%s google_refresh_token=%s",
            user.email,
            tokens.access_token,
            tokens.refresh_token,
        )

        kairos_user, kairos_tokens = self._auth_sync_bus.sync_google_user(user)

        return GoogleAuthResponse(
            user=user,
            tokens=tokens,
            kairos_user=kairos_user,
            kairos_tokens=kairos_tokens,
        )

    async def _verify_clerk_google_token(
        self,
        user: GoogleUserProfile,
        tokens: GoogleTokenSet,
    ) -> None:
        if tokens.id_token:
            claims = self.verify_id_token(tokens.id_token)
            token_email = str(claims.get("email") or "").strip().lower()
            token_sub = str(claims.get("sub") or claims.get("user_id") or "").strip()
            if token_email != user.email.lower() or token_sub != user.google_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="El id_token de Google no coincide con el usuario Clerk proporcionado.",
                )

        userinfo = await self.fetch_userinfo(tokens.access_token)
        userinfo_email = str(userinfo.get("email") or "").strip().lower()
        userinfo_sub = str(userinfo.get("sub") or userinfo.get("user_id") or "").strip()
        if not userinfo_email or not userinfo_sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El access_token de Google no es válido o no contiene información de usuario.",
            )

        if userinfo_email != user.email.lower() or userinfo_sub != user.google_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El access_token de Google no coincide con el usuario Clerk proporcionado.",
            )

    async def authenticate_clerk_session(
        self,
        user: GoogleUserProfile,
        tokens: GoogleTokenSet,
    ) -> GoogleAuthResponse:
        await self._verify_clerk_google_token(user, tokens)
        logger.info(
            "Google OAuth authenticate_clerk_session: user=%s google_access_token=%s google_refresh_token=%s",
            user.email,
            tokens.access_token,
            tokens.refresh_token,
        )
        kairos_user, kairos_tokens = self._auth_sync_bus.sync_google_user(user)
        return GoogleAuthResponse(
            user=user,
            tokens=tokens,
            kairos_user=kairos_user,
            kairos_tokens=kairos_tokens,
        )

    async def blacklist_access_token(self, token: str) -> None:
        await self._blacklist_token(token)

    def _build_user_profile(self, data: dict[str, object]) -> GoogleUserProfile:
        email = str(data.get("email") or "").strip()
        name = str(data.get("name") or "").strip()
        picture = data.get("picture")
        google_id = str(data.get("sub") or data.get("google_id") or "").strip()
        email_verified = bool(data.get("email_verified", False))

        if not email or not name or not google_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible obtener los datos básicos del usuario autenticado.",
            )

        return GoogleUserProfile(
            email=email,
            name=name,
            picture=str(picture) if picture else None,
            google_id=google_id,
            email_verified=email_verified,
        )

    def _create_state(self, client_id: str, redirect_uri: str) -> str:
        payload = StatePayload(
            nonce=secrets.token_urlsafe(24),
            issued_at=int(time.time()),
            client_id=client_id,
            redirect_uri=redirect_uri,
        )
        payload_bytes = json.dumps(asdict(payload), separators=(",", ":")).encode(
            "utf-8"
        )
        payload_token = (
            base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
        )
        signature = hmac.new(
            self._state_secret, payload_token.encode("utf-8"), hashlib.sha256
        ).digest()
        signature_token = (
            base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
        )
        return f"{payload_token}.{signature_token}"

    def _extract_state_payload(self, state: str) -> StatePayload:
        try:
            payload_token, signature_token = state.split(".", 1)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El parámetro state no es válido.",
            ) from exc

        expected_signature = hmac.new(
            self._state_secret,
            payload_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_signature_token = (
            base64.urlsafe_b64encode(expected_signature).decode("utf-8").rstrip("=")
        )

        if not hmac.compare_digest(signature_token, expected_signature_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudo validar el estado de autenticación.",
            )

        padding = "=" * (-len(payload_token) % 4)
        payload_data = json.loads(
            base64.urlsafe_b64decode(f"{payload_token}{padding}").decode("utf-8")
        )

        issued_at = int(payload_data.get("issued_at", 0))
        nonce = str(payload_data.get("nonce") or "").strip()
        client_id = str(payload_data.get("client_id") or "").strip()
        redirect_uri = str(payload_data.get("redirect_uri") or "").strip()

        if not nonce:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El estado de autenticación no contiene nonce.",
            )

        if not client_id or client_id not in self.settings.allowed_google_client_ids():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El estado de autenticación no contiene un client_id válido.",
            )

        if (
            not redirect_uri
            or redirect_uri not in self.settings.allowed_redirect_uris()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El estado de autenticación no contiene un redirect_uri válido.",
            )

        if int(time.time()) - issued_at > self.settings.state_ttl_seconds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La autenticación inició demasiado tiempo atrás y expiró.",
            )

        return StatePayload(
            nonce=nonce,
            issued_at=issued_at,
            client_id=client_id,
            redirect_uri=redirect_uri,
        )

    def _resolve_client(self, platform: str | None) -> tuple[str, bool]:
        normalized = (platform or "").strip().lower()
        if normalized == "android" and self.settings.google_client_id_android:
            return self.settings.google_client_id_android, False
        if normalized == "ios" and self.settings.google_client_id_ios:
            return self.settings.google_client_id_ios, False
        return self.settings.google_client_id, True

    def _resolve_redirect_uri(self, redirect_uri: str | None) -> str:
        if redirect_uri:
            value = redirect_uri.strip()
            if value not in self.settings.allowed_redirect_uris():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El redirect_uri no está permitido.",
                )
            return value

        return self.settings.google_redirect_uri

    def _should_use_client_secret(self, client_id: str) -> bool:
        return client_id == self.settings.google_client_id


@lru_cache(maxsize=1)
def get_google_oauth_service() -> GoogleOAuthService:
    return GoogleOAuthService(Settings())
