from fastapi import FastAPI

app = FastAPI(title="Kairos Schedule Service")


@app.get("/health")
def health():
    return {"service": "schedule_service", "status": "ok"}
