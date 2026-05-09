from fastapi import FastAPI

app = FastAPI(title="Kairos Auth Service")


@app.get("/health")
def health():
    return {"service": "auth_service", "status": "ok"}
