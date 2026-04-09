import logging
from sqlalchemy.orm import Session

from models.user import UserDB, UserRole
from services.keycloak_admin import KeycloakAdminClient
from config.keycloak import KeycloakConfig

logger = logging.getLogger(__name__)


class UserSyncService:
    """Синхронизация пользователей из Keycloak в локальную БД"""

    def __init__(self, keycloak_client: KeycloakAdminClient):
        self.keycloak_client = keycloak_client

    def sync_all_users(self, db: Session) -> dict:
        """
        Полная синхронизация пользователей из Keycloak.
        Возвращает статистику: created, updated, total.
        """
        stats = {"created": 0, "updated": 0, "errors": 0, "total": 0}

        try:
            keycloak_users = self.keycloak_client.get_all_users()
            stats["total"] = len(keycloak_users)
            logger.info(f"Starting sync of {len(keycloak_users)} users from Keycloak")

            for kc_user in keycloak_users:
                try:
                    result = self._sync_single_user(db, kc_user)
                    if result == "created":
                        stats["created"] += 1
                    elif result == "updated":
                        stats["updated"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(
                        f"Error syncing user {kc_user.get('username', 'unknown')}: {e}"
                    )
                    continue

            db.commit()
            logger.info(
                f"User sync completed: {stats['created']} created, "
                f"{stats['updated']} updated, {stats['errors']} errors "
                f"out of {stats['total']} total"
            )
            return stats

        except Exception as e:
            db.rollback()
            logger.error(f"User sync failed: {e}")
            raise

    def _sync_single_user(self, db: Session, kc_user: dict) -> str:
        """
        Синхронизировать одного пользователя.
        Возвращает 'created', 'updated' или 'unchanged'.
        """
        keycloak_id = kc_user.get("id")
        username = kc_user.get("username")

        if not keycloak_id or not username:
            logger.warning(f"Skipping user without id or username: {kc_user}")
            return "unchanged"

        # Не синхронизируем неактивных пользователей
        if not kc_user.get("enabled", True):
            logger.debug(f"Skipping disabled user: {username}")
            return "unchanged"

        # Получаем роли пользователя
        keycloak_roles = self.keycloak_client.get_user_roles(keycloak_id)
        role = KeycloakAdminClient.map_keycloak_role(keycloak_roles)
        full_name = KeycloakAdminClient.build_full_name(kc_user)

        # Ищем по keycloak_id
        existing_user = db.query(UserDB).filter(
            UserDB.keycloak_id == keycloak_id
        ).first()

        if existing_user:
            return self._update_user(existing_user, username, full_name, role)
        else:
            # Проверяем конфликт по username
            user_by_name = db.query(UserDB).filter(
                UserDB.username == username
            ).first()

            if user_by_name:
                # Username занят другим пользователем — обновляем keycloak_id
                logger.warning(
                    f"Username '{username}' exists with different keycloak_id, "
                    f"updating keycloak_id to {keycloak_id}"
                )
                user_by_name.keycloak_id = keycloak_id
                return self._update_user(user_by_name, username, full_name, role)

            return self._create_user(db, keycloak_id, username, full_name, role)

    def _update_user(
        self,
        user: UserDB,
        username: str,
        full_name: str,
        role: UserRole,
    ) -> str:
        """Обновить существующего пользователя, если данные изменились"""
        changed = False

        if user.username != username:
            user.username = username
            changed = True
        if user.full_name != full_name:
            user.full_name = full_name
            changed = True
        if user.role != role:
            user.role = role
            changed = True

        if changed:
            logger.info(f"Updated user: {username} (keycloak_id: {user.keycloak_id})")
            return "updated"

        return "unchanged"

    def _create_user(
        self,
        db: Session,
        keycloak_id: str,
        username: str,
        full_name: str,
        role: UserRole,
    ) -> str:
        """Создать нового пользователя"""
        new_user = UserDB(
            keycloak_id=keycloak_id,
            username=username,
            full_name=full_name,
            role=role,
        )
        db.add(new_user)
        logger.info(f"Created user: {username} (keycloak_id: {keycloak_id}, role: {role.value})")
        return "created"