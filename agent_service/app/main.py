from fastapi import FastAPI

app = FastAPI(title="Kairos Agent Service")


@app.get("/health")
def health():
    return {"service": "agent_service", "status": "ok"}
