from fastapi import FastAPI
from database import engine, Base
from api.endpoints import users, tasks

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Task Tracking Service", version="1.0.0")
app.include_router(users.router)
app.include_router(tasks.router)


@app.get("/")
def read_root():
    return {"message": "Task Tracking Service API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}

#Запуск через консоль: uvicorn main:app --reload
