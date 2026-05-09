from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.schemas import GoogleAuthResponse, GoogleMeResponse, GoogleRefreshRequest, GoogleRefreshResponse
from app.services.google_oauth import GoogleOAuthService, get_google_oauth_service


router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el header Authorization.",
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization debe ser 'Bearer <token>'.",
        )

    return parts[1]


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


@router.get("/me", response_model=GoogleMeResponse, summary="Get current Google user")
async def google_me(
    authorization: str = Header(..., description="Bearer access_token or id_token"),
    oauth_service: GoogleOAuthService = Depends(get_google_oauth_service),
) -> GoogleMeResponse:
    token = _extract_bearer_token(authorization)
    user = await oauth_service.get_current_user(token)
    return GoogleMeResponse(user=user)
