from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
	model_config = ConfigDict(extra="allow", populate_by_name=True)


class HealthResponse(BaseModel):
	status: str
	service: str
	environment: str


class ReadyResponse(BaseModel):
	status: str
	service: str


class FitTimeRange(BaseSchema):
	start_time: str
	end_time: str
	start_time_ms: int = Field(..., alias="startTimeMillis")
	end_time_ms: int = Field(..., alias="endTimeMillis")


class FitMetricBucket(BaseSchema):
	start_time_ms: int = Field(..., alias="startTimeMillis")
	end_time_ms: int = Field(..., alias="endTimeMillis")
	value: float | int | None = None
	raw_points: list[dict[str, Any]] | None = None


class FitMetric(BaseSchema):
	name: str
	data_type: str = Field(..., alias="dataTypeName")
	unit: str | None = None
	total: float | int | None = None
	buckets: list[FitMetricBucket] = Field(default_factory=list)


class FitMeResponse(BaseSchema):
	user_id: str
	scopes: list[str]
	time_range: FitTimeRange
	metrics: list[FitMetric]
	sessions: list[dict[str, Any]] = Field(default_factory=list)
	data_sources: list[dict[str, Any]] = Field(default_factory=list)
