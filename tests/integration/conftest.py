# tests/integration/conftest.py
import pytest
from sqlalchemy.orm import Session

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


@pytest.fixture(autouse=True)
def override_current_user(sample_user):
    """Подменяет get_current_user — только для интеграционных тестов"""
    app.dependency_overrides[get_current_user] = lambda: sample_user.id
    yield
    app.dependency_overrides.pop(get_current_user, None)