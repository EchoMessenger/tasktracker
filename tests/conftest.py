import pytest
import os
import sys
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["TESTING"] = "1"


@pytest.fixture(scope="session")
def test_database_url():
    """URL тестовой базы данных"""
    return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine(test_database_url):
    """Движок тестовой БД"""
    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    return engine


@pytest.fixture(scope="session")
def create_tables(engine):
    """Создание таблиц перед всеми тестами"""
    from database import Base
    try:
        from models.user import UserDB
    except ImportError as e:
        print(f"Не удалось импортировать UserDB: {e}")

    try:
        from models.task import TaskDB
    except ImportError:
        print(f"Не удалось импортировать TaskDB: {e}")

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(engine, create_tables) -> Generator[Session, None, None]:
    """Фикстура для сессии БД с rollback после каждого теста"""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def sample_user_data():
    """Тестовые данные пользователя"""
    return {
        "username": "testuser",
        "full_name": "Test User",
        "role": "user"
    }