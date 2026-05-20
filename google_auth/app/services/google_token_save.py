from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from app.config import Settings


class GoogleTokenSaveService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def save_tokens(
        self,
        access_token: str,
        refresh_token: str | None = None,
    ) -> dict[str, object]:
        self._assert_access_token(access_token)
        await self._verify_google_access_token(access_token)

        calendar_valid, calendar_error = await self._notify_service(
            service_name="Google Calendar",
            url=f"{self.settings.calendar_service_url.rstrip('/')}/google/save-token",
            access_token=access_token,
            refresh_token=refresh_token,
        )

        fit_valid, fit_error = await self._notify_service(
            service_name="Google Fit",
            url=f"{self.settings.google_fit_url.rstrip('/')}/fit/save-token",
            access_token=access_token,
            refresh_token=refresh_token,
        )

        return {
            "calendar_valid": calendar_valid,
            "fit_valid": fit_valid,
            "calendar_error": calendar_error,
            "fit_error": fit_error,
        }

    def _assert_access_token(self, access_token: str) -> None:
        if not access_token or not str(access_token).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere google_access_token.",
            )

    async def _verify_google_access_token(self, access_token: str) -> None:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds
        ) as client:
            response = await client.get(
                self.settings.google_userinfo_uri, headers=headers
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El google_access_token no es válido o expiró.",
            )

    async def _notify_service(
        self,
        service_name: str,
        url: str,
        access_token: str,
        refresh_token: str | None = None,
    ) -> tuple[bool, str | None]:
        payload: dict[str, str | None] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds
        ) as client:
            response = await client.post(url, json=payload)

        if response.status_code < 400:
            return True, None

        detail = None
        try:
            detail = response.json().get("detail")
        except ValueError:
            pass

        if not detail:
            detail = response.text or f"{service_name} devolvió {response.status_code}."

        return False, f"{service_name}: {detail}"


def get_google_token_save_service() -> GoogleTokenSaveService:
    return GoogleTokenSaveService(Settings())
