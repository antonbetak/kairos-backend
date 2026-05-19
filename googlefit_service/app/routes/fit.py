from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import get_settings
from app.schemas import FitMeResponse, FitTimeRange
from app.security import FitAuthContext, require_google_login, require_google_token
from app.services.google_fit import GoogleFitService


router = APIRouter(prefix="/fit", tags=["Google Fit"])
settings = get_settings()


def get_fit_service() -> GoogleFitService:
    return GoogleFitService(settings)


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Formato de fecha invalido."
        ) from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


@router.get("/me", response_model=FitMeResponse, summary="Get Google Fit summary")
@require_google_login
async def fit_me(
    start: str | None = Query(None, description="ISO datetime"),
    end: str | None = Query(None, description="ISO datetime"),
    bucket_days: int | None = Query(None, ge=1, le=30),
    auth: FitAuthContext = Depends(require_google_token),
    service: GoogleFitService = Depends(get_fit_service),
) -> FitMeResponse:
    now = datetime.now(timezone.utc)
    end_dt = _parse_datetime(end) if end else now
    start_dt = _parse_datetime(start) if start else end_dt - timedelta(days=30)

    start_ms = _to_ms(start_dt)
    end_ms = _to_ms(end_dt)

    data = await service.get_fit_data(
        auth.access_token,
        start_ms,
        end_ms,
        bucket_days or settings.fit_bucket_days,
    )

    time_range = FitTimeRange(
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat(),
        start_time_ms=start_ms,
        end_time_ms=end_ms,
    )

    return FitMeResponse(
        user_id=auth.user_id,
        scopes=auth.scopes,
        time_range=time_range,
        metrics=data["metrics"],
        sessions=data["sessions"],
        data_sources=data["data_sources"],
    )
