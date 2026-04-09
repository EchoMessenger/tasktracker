import logging
import time

from config.keycloak import KeycloakConfig
from services.keycloak_admin import KeycloakAdminClient
from services.user_sync import UserSyncService
from auth.dependencies import init_auth
from database import SessionLocal

logger = logging.getLogger(__name__)

MAX_RETRIES = 10
RETRY_DELAY_SECONDS = 5


def startup_sync() -> None:
    """
    Синхронизация при старте приложения.
    Блокирует запуск, пока все пользователи не синхронизированы.
    """
    config = KeycloakConfig.from_env()

    # Инициализируем аутентификацию (загружаем JWKS)
    logger.info("Initializing auth module...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            init_auth(config)
            logger.info("Auth module initialized successfully")
            break
        except Exception as e:
            logger.warning(
                f"Failed to initialize auth (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Cannot initialize auth after {MAX_RETRIES} attempts"
                ) from e
            time.sleep(RETRY_DELAY_SECONDS)

    # Синхронизируем пользователей
    logger.info("Starting user synchronization from Keycloak...")
    keycloak_client = KeycloakAdminClient(config)
    sync_service = UserSyncService(keycloak_client)

    for attempt in range(1, MAX_RETRIES + 1):
        db = SessionLocal()
        try:
            stats = sync_service.sync_all_users(db)
            logger.info(
                f"User sync completed on attempt {attempt}: "
                f"{stats['created']} created, {stats['updated']} updated, "
                f"{stats['errors']} errors out of {stats['total']} total"
            )

            if stats["errors"] > 0 and stats["created"] == 0 and stats["updated"] == 0:
                raise RuntimeError(
                    f"All {stats['errors']} users failed to sync"
                )

            logger.info("Startup synchronization completed successfully")
            return

        except RuntimeError:
            raise
        except Exception as e:
            logger.warning(
                f"User sync failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"User sync failed after {MAX_RETRIES} attempts"
                ) from e
            time.sleep(RETRY_DELAY_SECONDS)
        finally:
            db.close()