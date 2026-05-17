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


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StatePayload:
    nonce: str
    issued_at: int


class GoogleOAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._state_secret = settings.google_client_secret.encode("utf-8")

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

    def build_authorization_url(self) -> str:
        state = self._create_state()
        query = {
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "response_type": "code",
            "scope": self.settings.google_scope,
            "state": state,
            "nonce": self._extract_state_payload(state).nonce,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent select_account",
        }
        return f"{self.settings.google_auth_uri}?{urlencode(query)}"

    async def exchange_code(self, code: str) -> dict[str, object]:
        payload = {
            "code": code,
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "redirect_uri": self.settings.google_redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(self.settings.google_token_uri, data=payload)

        if response.status_code >= 400:
            logger.warning("Google token exchange failed: %s", response.text)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible intercambiar el código de autorización con Google.",
            )

        return response.json()

    async def refresh_tokens(self, refresh_token: str) -> GoogleTokenSet:
        if await self._token_status(refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El refresh token de Google fue invalidado.",
            )

        payload = {
            "refresh_token": refresh_token,
            "client_id": self.settings.google_client_id,
            "client_secret": self.settings.google_client_secret,
            "grant_type": "refresh_token",
        }

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

        try:
            claims = google_id_token.verify_oauth2_token(
                token,
                request,
                audience=self.settings.google_client_id,
                clock_skew_in_seconds=self.settings.clock_skew_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google id_token validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El id_token de Google no es válido.",
            ) from exc

        if expected_nonce and claims.get("nonce") != expected_nonce:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El nonce del token no coincide con la autenticación iniciada.",
            )

        return claims

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
        token_response = await self.exchange_code(code)

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

        return GoogleAuthResponse(user=user, tokens=tokens)

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

    def _create_state(self) -> str:
        payload = StatePayload(
            nonce=secrets.token_urlsafe(24), issued_at=int(time.time())
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

        if not nonce:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El estado de autenticación no contiene nonce.",
            )

        if int(time.time()) - issued_at > self.settings.state_ttl_seconds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La autenticación inició demasiado tiempo atrás y expiró.",
            )

        return StatePayload(nonce=nonce, issued_at=issued_at)


@lru_cache(maxsize=1)
def get_google_oauth_service() -> GoogleOAuthService:
    return GoogleOAuthService(Settings())
