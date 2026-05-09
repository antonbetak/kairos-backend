from fastapi import FastAPI

app = FastAPI(title="Kairos API Gateway")


@app.get("/health")
def health():
    return {"service": "api-gateway", "status": "ok"}
