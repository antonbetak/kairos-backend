from fastapi import FastAPI

app = FastAPI(title="Kairos Calendar Service")


@app.get("/health")
def health():
    return {"service": "calendar_service", "status": "ok"}
