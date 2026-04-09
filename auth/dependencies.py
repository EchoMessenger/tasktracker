import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from auth.jwt_validator import JWTValidator
from config.keycloak import KeycloakConfig
from database import get_db
from models.user import UserDB
from services.keycloak_admin import KeycloakAdminClient

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

# Глобальные объекты — инициализируются при старте
_keycloak_config: KeycloakConfig | None = None
_jwt_validator: JWTValidator | None = None


def init_auth(config: KeycloakConfig) -> None:
    """Инициализация модуля аутентификации — вызывается при старте приложения"""
    global _keycloak_config, _jwt_validator
    _keycloak_config = config
    _jwt_validator = JWTValidator(config)
    # Предварительно загружаем JWKS
    _jwt_validator.refresh_jwks()
    logger.info("Auth module initialized, JWKS loaded")


def get_jwt_validator() -> JWTValidator:
    if _jwt_validator is None:
        raise RuntimeError("Auth module not initialized. Call init_auth() first.")
    return _jwt_validator


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> UserDB:
    """
    FastAPI dependency — валидирует JWT и возвращает пользователя из БД.
    Если пользователя нет в БД — создаёт автоматически (just-in-time provisioning).
    """
    validator = get_jwt_validator()
    token = credentials.credentials

    # Валидация токена
    payload = validator.validate_token(token)
    user_info = validator.extract_user_info(payload)

    keycloak_id = user_info.get("keycloak_id")
    if not keycloak_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    # Ищем пользователя по keycloak_id
    user = db.query(UserDB).filter(UserDB.keycloak_id == keycloak_id).first()

    if not user:
        # Just-in-time provisioning — создаём пользователя из токена
        logger.info(f"JIT provisioning user: {user_info.get('username')} ({keycloak_id})")
        role = KeycloakAdminClient.map_keycloak_role(user_info.get("roles", []))

        user = UserDB(
            keycloak_id=keycloak_id,
            username=user_info.get("username", keycloak_id),
            full_name=user_info.get("full_name", ""),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


async def get_current_user_id(
    current_user: UserDB = Depends(get_current_user),
) -> int:
    """Dependency — возвращает только ID текущего пользователя"""
    return current_user.id