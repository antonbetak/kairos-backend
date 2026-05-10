from fastapi import FastAPI
from fastapi import Depends
from sqlalchemy.orm import Session

from app import models
from app.database import Base
from app.database import SessionLocal
from app.database import engine
from app.schemas import TareaCrear
from app.schemas import TareaRespuesta

app = FastAPI(title="Kairos Task Service")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"service": "task_service", "status": "ok"}


@app.post("/tasks", response_model=TareaRespuesta)
def crear_tarea(tarea: TareaCrear, db: Session = Depends(get_db)):
    nueva_tarea = models.Tarea(
        id_usuario="usuario-demo",
        titulo=tarea.titulo,
        descripcion=tarea.descripcion,
        completada=False,
    )

    db.add(nueva_tarea)
    db.commit()
    db.refresh(nueva_tarea)

    return nueva_tarea
