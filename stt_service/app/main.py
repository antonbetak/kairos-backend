from fastapi import FastAPI


app = FastAPI(
	title="Kairos STT Service",
	version="1.0.0",
	description="Speech-to-text service (placeholder).",
)


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok", "service": "stt_service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
	return {"status": "ready", "service": "stt_service"}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
	return {
		"service": "stt_service",
		"status": "running",
		"docs": "/docs",
		"health": "/health",
	}
