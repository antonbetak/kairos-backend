from fastapi import FastAPI

app = FastAPI(title="Kairos Stats Service")


@app.get("/health")
def health():
    return {"service": "stats_service", "status": "ok"}
