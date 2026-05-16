from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import Settings
from app.schemas import FitMetric, FitMetricBucket


logger = logging.getLogger(__name__)


FIT_DATA_TYPES: dict[str, dict[str, str]] = {
    "com.google.step_count.delta": {"name": "steps", "unit": "count"},
    "com.google.distance.delta": {"name": "distance_meters", "unit": "m"},
    "com.google.calories.expended": {"name": "calories_kcal", "unit": "kcal"},
    "com.google.active_minutes": {"name": "active_minutes", "unit": "min"},
    "com.google.heart_rate.bpm": {"name": "heart_rate_bpm", "unit": "bpm"},
    "com.google.weight": {"name": "weight_kg", "unit": "kg"},
    "com.google.activity.segment": {"name": "activity_segments", "unit": "count"},
}


class GoogleFitService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.google_fit_api_base.rstrip("/")

    async def get_fit_data(
        self,
        access_token: str,
        start_ms: int,
        end_ms: int,
        bucket_days: int,
    ) -> dict[str, Any]:
        metrics = await self.aggregate_metrics(access_token, start_ms, end_ms, bucket_days)
        sessions = await self.list_sessions(access_token, start_ms, end_ms)
        data_sources = await self.list_data_sources(access_token)

        return {
            "metrics": metrics,
            "sessions": sessions,
            "data_sources": data_sources,
        }

    async def aggregate_metrics(
        self,
        access_token: str,
        start_ms: int,
        end_ms: int,
        bucket_days: int,
    ) -> list[FitMetric]:
        data_types = list(FIT_DATA_TYPES.keys())
        bucket_ms = max(1, bucket_days) * 24 * 60 * 60 * 1000
        payload = {
            "aggregateBy": [{"dataTypeName": dt} for dt in data_types],
            "bucketByTime": {"durationMillis": bucket_ms},
            "startTimeMillis": start_ms,
            "endTimeMillis": end_ms,
        }

        url = f"{self.base_url}/dataset:aggregate"
        response = await self._request("POST", url, access_token, json=payload)
        buckets = response.get("bucket", [])

        metrics: dict[str, FitMetric] = {}
        for data_type in data_types:
            meta = FIT_DATA_TYPES[data_type]
            metrics[data_type] = FitMetric(
                name=meta["name"],
                data_type=data_type,
                unit=meta.get("unit"),
                total=0,
                buckets=[],
            )

        for bucket in buckets:
            start_time = int(bucket.get("startTimeMillis", 0))
            end_time = int(bucket.get("endTimeMillis", 0))
            datasets = bucket.get("dataset", [])

            for index, dataset in enumerate(datasets):
                data_type = data_types[index] if index < len(data_types) else dataset.get("dataSourceId")
                metric = metrics.get(data_type)
                if metric is None:
                    continue

                points = dataset.get("point", [])
                value = self._sum_points(points, data_type)
                bucket_item = FitMetricBucket(
                    start_time_ms=start_time,
                    end_time_ms=end_time,
                    value=value,
                    raw_points=points if data_type == "com.google.activity.segment" else None,
                )
                metric.buckets.append(bucket_item)
                if metric.total is None:
                    metric.total = value
                else:
                    try:
                        metric.total = metric.total + (value or 0)
                    except TypeError:
                        metric.total = value

        return list(metrics.values())

    async def list_sessions(self, access_token: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        url = f"{self.base_url}/sessions"
        params = {
            "startTime": self._ms_to_rfc3339(start_ms),
            "endTime": self._ms_to_rfc3339(end_ms),
        }
        response = await self._request("GET", url, access_token, params=params)
        return response.get("session", [])

    async def list_data_sources(self, access_token: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/dataSources"
        response = await self._request("GET", url, access_token)
        return response.get("dataSource", [])

    def _sum_points(self, points: list[dict[str, Any]], data_type: str) -> float | int:
        if data_type == "com.google.activity.segment":
            return len(points)

        total: float = 0.0
        for point in points:
            for value in point.get("value", []):
                if "intVal" in value:
                    total += float(value.get("intVal") or 0)
                elif "fpVal" in value:
                    total += float(value.get("fpVal") or 0)
        return int(total) if total.is_integer() else total

    def _ms_to_rfc3339(self, ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

    async def _request(
        self,
        method: str,
        url: str,
        access_token: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.request(method, url, headers=headers, params=params, json=json)

        if response.status_code >= 400:
            logger.warning("Google Fit API failed: %s", response.text)
            raise HTTPException(
                status_code=response.status_code,
                detail="Google Fit API rechazo la solicitud.",
            )

        if response.status_code == status.HTTP_204_NO_CONTENT or not response.content:
            return {}

        return response.json()
