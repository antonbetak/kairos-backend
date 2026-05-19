from __future__ import annotations

import httpx
import logging
from fastapi import HTTPException, status

from app.config import Settings, get_settings

settings = get_settings()


class ClerkGoogleTokenService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger("api_gateway.clerk_google_token_service")

    @staticmethod
    def _normalize_scopes(scopes: object) -> list[str]:
        if isinstance(scopes, str):
            return [scope.strip() for scope in scopes.split() if scope.strip()]
        if isinstance(scopes, list):
            return [str(scope).strip() for scope in scopes if str(scope).strip()]
        return []

    async def get_google_access_token(self, clerk_user_id: str) -> dict[str, object]:
        if not clerk_user_id or not clerk_user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere clerk_user_id para obtener el token de Google.",
            )

        if not self.settings.clerk_secret_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falta la clave secreta de Clerk en el servidor.",
            )

        url = f"{self.settings.clerk_api_base.rstrip('/')}/users/{clerk_user_id}/oauth_access_tokens/google"
        headers = {"Authorization": f"Bearer {self.settings.clerk_secret_key}"}

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.get(url, headers=headers)
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No fue posible contactar la API de Clerk para obtener el token de Google.",
            ) from exc

        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El usuario no tiene una cuenta de Google conectada en Clerk.",
            )

        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clerk rejected the request. Verifica CLERK_SECRET_KEY y permisos.",
            )

        if response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Límite de tasa alcanzado en la API de Clerk.",
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Error de Clerk API al obtener token de Google: "
                    f"{response.status_code} {response.text}"
                ),
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="La respuesta de Clerk no tiene el formato esperado.",
            )

        logger = logging.getLogger("api_gateway.clerk_google_token_service")
        try:
            logger.debug("Clerk oauth_access_tokens payload for clerk_user_id=%s: %s", clerk_user_id, payload)
        except Exception:
            pass

        tokens = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip().lower()
            if provider not in {"google", "oauth_google"}:
                continue
            token_value = str(item.get("token") or "").strip()
            if not token_value:
                continue
            refresh_value = str(
                item.get("refresh_token")
                or item.get("refreshToken")
                or item.get("refresh-token")
                or ""
            ).strip()
            tokens.append(
                {
                    "token": token_value,
                    "refresh_token": refresh_value or None,
                    "scopes": self._normalize_scopes(item.get("scopes") or []),
                }
            )

        try:
            logger.debug("Parsed Google tokens for clerk_user_id=%s: %s", clerk_user_id, tokens)
        except Exception:
            pass

        if not tokens:
            try:
                logger.debug(
                    "No Google tokens found for clerk_user_id=%s, payload=%s",
                    clerk_user_id,
                    payload,
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró un token de Google válido para el usuario.",
            )

        required_scopes = set(self.settings.google_required_scopes_list())
        selected_token = None
        selected_scopes: list[str] = []
        selected_refresh_token: str | None = None

        selected: dict[str, object] | None = None
        if tokens:
            # Prefer a token with the required scopes and a refresh token.
            for item in tokens:
                token_scopes = set(item["scopes"])
                if required_scopes and required_scopes.issubset(token_scopes):
                    if item.get("refresh_token"):
                        selected = item
                        break
                    if selected is None:
                        selected = item

            # If no token with required scopes was found, choose the best available token.
            if selected is None:
                # Prefer tokens with refresh_token, then the token with the most scopes.
                selected = max(
                    tokens,
                    key=lambda item: (
                        bool(item.get("refresh_token")),
                        len(set(item["scopes"])),
                    ),
                )

            selected_token = selected["token"]
            selected_scopes = selected["scopes"]
            selected_refresh_token = selected.get("refresh_token")

        if required_scopes and not required_scopes.issubset(set(selected_scopes)):
            missing = sorted(required_scopes.difference(set(selected_scopes)))
            try:
                logger.debug(
                    "Google token missing required scopes for clerk_user_id=%s: selected_scopes=%s required_scopes=%s missing=%s",
                    clerk_user_id,
                    selected_scopes,
                    list(required_scopes),
                    missing,
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "El token de Google obtenido no incluye los scopes requeridos: "
                    f"{', '.join(missing)}"
                ),
            )

        result = {
            "access_token": selected_token,
            "refresh_token": selected_refresh_token,
            "provider": "google",
            "scopes": selected_scopes,
        }

        # Log token for testing purposes (prints in the gateway terminal)
        try:
            self.logger.debug("Obtained Google token for clerk_user_id=%s: %s", clerk_user_id, selected_token)
        except Exception:
            # Never raise because of logging
            pass

        return result


def get_clerk_google_token_service() -> ClerkGoogleTokenService:
    return ClerkGoogleTokenService(settings)
