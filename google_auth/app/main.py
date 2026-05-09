from fastapi import FastAPI

app = FastAPI(title="Kairos Google Auth Service")


@app.get("/health")
def health():
    return {"service": "google_auth_service", "status": "ok"}
