from fastapi import FastAPI

app = FastAPI(title="Kairos Task Service")


@app.get("/health")
def health():
    return {"service": "task_service", "status": "ok"}
