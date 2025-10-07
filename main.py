from fastapi import FastAPI
from database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import v1_users_router, v1_tasks_router, v2_users_router
import json
import os

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Task Tracking Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(v1_users_router)
app.include_router(v1_tasks_router)
app.include_router(v2_users_router)

@app.on_event("startup")
def save_openapi_spec():
    """Сохраняет OpenAPI спецификацию при запуске"""
    os.makedirs("docs", exist_ok=True)
    with open("docs/openapi.json", "w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, indent=2, ensure_ascii=False)

@app.get("/")
def read_root():
    return {"message": "Task Tracking Service API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}

#Запуск через консоль: uvicorn main:app --reload
