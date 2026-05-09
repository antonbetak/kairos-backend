from fastapi import FastAPI

app = FastAPI(title="Kairos STT Service")


@app.get("/health")
def health():
    return {"service": "stt_service", "status": "ok"}
