from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.schemas import GoogleAuthResponse, GoogleRefreshRequest, GoogleRefreshResponse
from app.services.google_oauth import GoogleOAuthService, get_google_oauth_service


router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])


@router.get("/login", summary="Start Google authentication")
async def start_google_login(
    oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
) -> RedirectResponse:
    authorization_url = oauth_service.build_authorization_url()
    return RedirectResponse(url=authorization_url, status_code=307)


@router.get("/callback", response_model=GoogleAuthResponse, summary="Google OAuth callback")
async def google_callback(
    code: str = Query(..., description="Authorization code returned by Google"),
    state: str = Query(..., description="Signed state generated at login time"),
    oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
) -> GoogleAuthResponse:
    return await oauth_service.authenticate(code=code, state=state)


@router.post("/refresh", response_model=GoogleRefreshResponse, summary="Refresh Google access token")
async def refresh_google_token(
    payload: GoogleRefreshRequest,
    oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
) -> GoogleRefreshResponse:
    tokens = await oauth_service.refresh_tokens(refresh_token=payload.refresh_token)
    return GoogleRefreshResponse(tokens=tokens)
