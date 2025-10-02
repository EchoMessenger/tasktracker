from fastapi import FastAPI
from database import engine, Base
from models import *
from api.endpoints import users

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Task Tracking Service", version="1.0.0")
app.include_router(users.router)


@app.get("/")
def read_root():
    return {"message": "Task Tracking Service API"}

