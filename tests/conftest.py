import pytest
import os
import sys
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["TESTING"] = "1"

from main import app
from database import get_db
from crud import create_user
from models.user import UserRole
from schemas import UserCreate
from api.endpoints.v2.tasks import get_current_user


@pytest.fixture(scope="session")
def test_database_url():
    return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine(test_database_url):
    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    return engine


@pytest.fixture(scope="session")
def create_tables(engine):
    from database import Base
    try:
        from models.user import UserDB
    except ImportError as e:
        print(f"Не удалось импортировать UserDB: {e}")
    try:
        from models.task import TaskDB
    except ImportError as e:
        print(f"Не удалось импортировать TaskDB: {e}")

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(engine, create_tables) -> Generator[Session, None, None]:
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def override_db(db_session):
    """Подменяет get_db — нужно для ВСЕХ тестов"""
    def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def sample_user_data():
    return {
        "username": "testuser",
        "full_name": "Test User",
        "role": "user"
    }