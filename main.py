from fastapi import FastAPI
from database import engine, Base, SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from api.endpoints import v1_users_router, v1_tasks_router, v2_users_router, v2_tasks_router
import json
import os
import logging
from contextlib import asynccontextmanager
from kafka_consumer import KafkaConsumer
from config.keycloak import KeycloakConfig
from services.keycloak_admin import KeycloakAdminClient
from services.user_sync import UserSyncService
from auth.dependencies import init_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
kafka_consumer = None

def get_db_session():
    """Функция для получения сессии БД для Kafka consumer"""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logger.error(f"Failed to create DB session: {e}")
        db.close()
        raise

def sync_users_on_startup():
    logger.info("Initializing Keycloak integration...")
    config = KeycloakConfig.from_env()

    logger.info(f"Keycloak issuer_uri={config.issuer_uri}")
    logger.info(f"Keycloak jwks_url={config.jwks_url}")
    logger.info(f"Keycloak admin_users_url={config.admin_users_url}")

    init_auth(config)
    logger.info("JWT validator initialized successfully")

    db = get_db_session()
    try:
        keycloak_client = KeycloakAdminClient(config)
        sync_service = UserSyncService(keycloak_client)

        stats = sync_service.sync_all_users(db)

        logger.info(
            "User synchronization completed successfully: "
            f"{stats['created']} created, "
            f"{stats['updated']} updated, "
            f"{stats['errors']} errors, "
            f"{stats['total']} total"
        )
    except Exception as e:
        logger.error(f"Startup user synchronization failed: {e}")
        raise RuntimeError("Application startup aborted: Keycloak sync failed") from e
    finally:
        db.close()

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     logger.info("Starting Task Tracking Service")
#     if not os.getenv("TESTING"):
#         Base.metadata.create_all(bind=engine)
#         logger.info("Database tables created/verified")
#
#         global kafka_consumer
#         try:
#             kafka_consumer = KafkaConsumer(get_db_session)
#             kafka_consumer.start()
#             logger.info("Kafka consumer started successfully")
#         except Exception as e:
#             logger.error(f"Failed to start Kafka consumer: {e}")
#             logger.warning("Kafka synchronization will not work")
#             kafka_consumer = None
#     else:
#         logger.info("Running in TEST mode — skipping DB init and Kafka")
#
#     yield
#
#     logger.info("Shutting down Task Tracking Service")
#     if not os.getenv("TESTING") and kafka_consumer:
#         kafka_consumer.stop()
#         logger.info("Kafka consumer stopped")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Task Tracking Service")

    if not os.getenv("TESTING"):
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
        sync_users_on_startup()
        logger.info("Keycloak user synchronization finished")
    else:
        logger.info("Running in TEST mode — skipping DB init and Keycloak sync")
    yield
    logger.info("Shutting down Task Tracking Service")

app = FastAPI(
    title="Task Tracking Service",
    version="1.0.0",
    lifespan=lifespan
)

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
app.include_router(v2_tasks_router)

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
    return {"status": "healthy", "user_sync": "active", "auth": "active"}


# @app.get("/kafka/info")
# def kafka_info():
#     """Информация о Kafka подключении"""
#     if not kafka_consumer:
#         return {"status": "not_initialized"}
#
#     return {
#         "status": "running" if kafka_consumer.running else "stopped",
#         "topic": kafka_consumer.topic,
#         "group_id": kafka_consumer.config.get('group.id'),
#         "bootstrap_servers": kafka_consumer.config.get('bootstrap.servers')
#     }
#Запуск через консоль: uvicorn main:app --reload
