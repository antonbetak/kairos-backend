from fastapi import FastAPI

app = FastAPI(title="Kairos Google Fit Service")


@app.get("/health")
def health():
    return {"service": "googlefit_service", "status": "ok"}
