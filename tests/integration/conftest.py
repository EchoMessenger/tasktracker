# tests/integration/conftest.py
import pytest
from sqlalchemy.orm import Session
from database import get_db
from main import app
from crud import create_user
from models.user import UserRole
from schemas import UserCreate
from api.endpoints.v2.tasks import get_current_user


@pytest.fixture
def sample_user(db_session: Session):
    """Тестовый пользователь с правами ADMIN — только для интеграционных тестов"""
    user_data = UserCreate(
        username="test_user_endpoint",
        full_name="Test User Endpoint",
        role=UserRole.ADMIN
    )
    return create_user(db_session, user_data)


# @pytest.fixture(autouse=True)
# def override_current_user(sample_user):
#     """Подменяет get_current_user — только для интеграционных тестов"""
#     app.dependency_overrides[get_current_user] = lambda: sample_user.id
#     yield
#     app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture(autouse=True)
def override_dependencies(sample_user, db_session):
    """Подменяет get_current_user И get_db для интеграционных тестов"""

    # Подменяем get_db чтобы app использовал тестовую SQLite сессию
    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # не закрываем — это делает фикстура db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: sample_user.id

    yield

    app.dependency_overrides.clear()