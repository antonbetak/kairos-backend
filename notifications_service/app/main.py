from fastapi import FastAPI

app = FastAPI(title="Kairos Notifications Service")


@app.get("/health")
def health():
    return {"service": "notifications_service", "status": "ok"}
