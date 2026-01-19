import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text  # <-- Добавляем импорт text


class TestSimpleUserCRUD:
    """Простые тесты"""

    def test_import_modules(self):
        """Тест что можем импортировать все необходимые модули"""
        from crud.user import get_user, create_user
        from schemas.user import UserCreate
        from models.user import UserDB, UserRole
        assert True  # Все импорты успешны

    def test_session_works(self, db_session: Session):
        """Тест что сессия БД работает"""
        assert db_session is not None
        result = db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    def test_tables_created(self, db_session: Session):
        """Тест что таблицы созданы"""
        from sqlalchemy import inspect, text
        inspector = inspect(db_session.get_bind())
        tables = inspector.get_table_names()
        assert 'users' in tables, "Таблица 'users' не создана"
        columns = inspector.get_columns('users')
        column_names = [col['name'] for col in columns]
        expected_columns = ['id', 'username', 'full_name', 'role']
        for col in expected_columns:
            assert col in column_names, f"Колонка '{col}' отсутствует в таблице users"


class TestUserCRUDFunctions:
    """Тесты для всех функций из crud/user.py"""

    def test_get_user_function(self, db_session: Session):
        """Тест функции get_user"""
        from crud.user import get_user, create_user
        from schemas.user import UserCreate
        from models.user import UserRole
        user_data = {
            "username": "test_get_user",
            "full_name": "Test Get User",
            "role": UserRole.USER
        }
        created_user = create_user(db_session, UserCreate(**user_data))
        result = get_user(db_session, created_user.id)
        assert result is not None
        assert result.id == created_user.id
        assert result.username == "test_get_user"
        result = get_user(db_session, 99999)
        assert result is None

    def test_get_user_by_username_function(self, db_session: Session):
        """Тест функции get_user_by_username"""
        from crud.user import get_user_by_username, create_user
        from schemas.user import UserCreate
        from models.user import UserRole
        user_data = {
            "username": "john_doe",
            "full_name": "John Doe",
            "role": UserRole.USER
        }
        create_user(db_session, UserCreate(**user_data))
        result = get_user_by_username(db_session, "john_doe")
        assert result is not None
        assert result.username == "john_doe"
        assert result.full_name == "John Doe"
        result = get_user_by_username(db_session, "nonexistent")
        assert result is None

    def test_create_user_function(self, db_session: Session):
        """Тест функции create_user"""
        from crud.user import create_user, get_user_by_username
        from schemas.user import UserCreate
        from models.user import UserRole
        user_data = {
            "username": "new_user",
            "full_name": "New User",
            "role": UserRole.USER
        }

        result = create_user(db_session, UserCreate(**user_data))
        assert result is not None
        assert result.username == "new_user"
        assert result.full_name == "New User"
        assert result.role == UserRole.USER
        saved_user = get_user_by_username(db_session, "new_user")
        assert saved_user is not None
        assert saved_user.id == result.id
        duplicate_result = create_user(db_session, UserCreate(**user_data))
        assert duplicate_result is None

    def test_get_users_function_with_pagination(self, db_session: Session):
        """Тест функции get_users с пагинацией"""
        from crud.user import get_users, create_user
        from schemas.user import UserCreate
        from models.user import UserRole
        for i in range(1, 16):
            user_data = {
                "username": f"user_{i:02d}",
                "full_name": f"User {i}",
                "role": UserRole.USER
            }
            create_user(db_session, UserCreate(**user_data))
        users = get_users(db_session, skip=0, limit=5)
        assert len(users) == 5
        assert users[0].username == "user_01"
        assert users[4].username == "user_05"
        users = get_users(db_session, skip=10, limit=5)
        assert len(users) == 5
        assert users[0].username == "user_11"
        assert users[4].username == "user_15"
        users = get_users(db_session, skip=0, limit=100)
        assert len(users) == 15

    def test_get_users_function_with_role_filter(self, db_session: Session):
        """Тест функции get_users с фильтром по роли"""
        from crud.user import get_users, create_user
        from schemas.user import UserCreate
        from models.user import UserRole
        users_data = [
            ("admin1", "Admin One", UserRole.ADMIN),
            ("user1", "User One", UserRole.USER),
            ("admin2", "Admin Two", UserRole.ADMIN),
            ("user2", "User Two", UserRole.USER),
            ("manager1", "Manager One", UserRole.MANAGER),
        ]

        for username, full_name, role in users_data:
            user_data = {"username": username, "full_name": full_name, "role": role}
            create_user(db_session, UserCreate(**user_data))

        admins = get_users(db_session, role=UserRole.ADMIN)
        assert len(admins) == 2
        assert all(user.role == UserRole.ADMIN for user in admins)

        users = get_users(db_session, role=UserRole.USER)
        assert len(users) == 2
        assert all(user.role == UserRole.USER for user in users)

        managers = get_users(db_session, role=UserRole.MANAGER)
        assert len(managers) == 1

    def test_get_users_function_with_search(self, db_session: Session):
        """Тест функции get_users с поиском"""
        from crud.user import get_users, create_user
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем пользователей для поиска
        users_data = [
            ("john_doe", "John Doe", UserRole.USER),
            ("jane_smith", "Jane Smith", UserRole.USER),
            ("bob_johnson", "Bob Johnson", UserRole.USER),
            ("alice_wonder", "Alice Wonderland", UserRole.USER),
        ]

        for username, full_name, role in users_data:
            user_data = {"username": username, "full_name": full_name, "role": role}
            create_user(db_session, UserCreate(**user_data))

        # Тест 1: Поиск по username (частичное совпадение)
        john_users = get_users(db_session, search="john")
        assert len(john_users) == 2  # john_doe и bob_johnson

        # Тест 2: Поиск по full_name (частичное совпадение)
        smith_users = get_users(db_session, search="smith")
        assert len(smith_users) == 1  # jane_smith

        # Тест 3: Поиск с учетом регистра (не должен учитывать)
        alice_users = get_users(db_session, search="ALICE")
        assert len(alice_users) == 1  # alice_wonder

        # Тест 4: Поиск который ничего не находит
        no_users = get_users(db_session, search="xyz")
        assert len(no_users) == 0

    def test_get_users_count_function(self, db_session: Session):
        """Тест функции get_users_count"""
        from crud.user import get_users_count, create_user
        from schemas.user import UserCreate
        from models.user import UserRole

        users_data = [
            ("admin1", "Admin One", UserRole.ADMIN),
            ("user1", "User One", UserRole.USER),
            ("admin2", "Admin Two", UserRole.ADMIN),
            ("user2", "User Two", UserRole.USER),
        ]

        for username, full_name, role in users_data:
            user_data = {"username": username, "full_name": full_name, "role": role}
            create_user(db_session, UserCreate(**user_data))

        total_count = get_users_count(db_session)
        assert total_count == 4

        admin_count = get_users_count(db_session, role=UserRole.ADMIN)
        assert admin_count == 2

        user_count = get_users_count(db_session, role=UserRole.USER)
        assert user_count == 2

        search_count = get_users_count(db_session, search="admin")
        assert search_count == 2

    def test_update_user_function(self, db_session: Session):
        """Тест функции update_user"""
        from crud.user import update_user, create_user, get_user
        from schemas.user import UserCreate, UserUpdate
        from models.user import UserRole

        user_data = {
            "username": "user_to_update",
            "full_name": "Original Name",
            "role": UserRole.USER
        }
        created_user = create_user(db_session, UserCreate(**user_data))

        update_data = UserUpdate(full_name="Updated Name")
        updated_user = update_user(db_session, created_user.id, update_data)

        assert updated_user is not None
        assert updated_user.full_name == "Updated Name"
        assert updated_user.username == "user_to_update"

        db_user = get_user(db_session, created_user.id)
        assert db_user.full_name == "Updated Name"

        update_data = UserUpdate(username="new_username")
        updated_user = update_user(db_session, created_user.id, update_data)

        assert updated_user is not None
        assert updated_user.username == "new_username"

        another_user = create_user(db_session, UserCreate(
            username="existing_user",
            full_name="Existing User",
            role=UserRole.USER
        ))

        update_data = UserUpdate(username="existing_user")
        result = update_user(db_session, created_user.id, update_data)
        assert result is None

        result = update_user(db_session, 99999, UserUpdate(full_name="Test"))
        assert result is None

    def test_delete_user_function(self, db_session: Session):
        """Тест функции delete_user"""
        from crud.user import delete_user, create_user, get_user
        from schemas.user import UserCreate
        from models.user import UserRole

        user_data = {
            "username": "user_to_delete",
            "full_name": "User To Delete",
            "role": UserRole.USER
        }
        created_user = create_user(db_session, UserCreate(**user_data))

        assert get_user(db_session, created_user.id) is not None

        delete_result = delete_user(db_session, created_user.id)
        assert delete_result is True

        assert get_user(db_session, created_user.id) is None

        delete_result = delete_user(db_session, 99999)
        assert delete_result is False

    def test_get_users_by_role_function(self, db_session: Session):
        """Тест функции get_users_by_role"""
        from crud.user import get_users_by_role, create_user
        from schemas.user import UserCreate
        from models.user import UserRole

        users_data = [
            ("admin1", "Admin One", UserRole.ADMIN),
            ("user1", "User One", UserRole.USER),
            ("admin2", "Admin Two", UserRole.ADMIN),
            ("user2", "User Two", UserRole.USER),
            ("user3", "User Three", UserRole.USER),
        ]

        for username, full_name, role in users_data:
            user_data = {"username": username, "full_name": full_name, "role": role}
            create_user(db_session, UserCreate(**user_data))

        # Тест 1: Получение всех администраторов
        admins = get_users_by_role(db_session, UserRole.ADMIN)
        assert len(admins) == 2
        assert all(user.role == UserRole.ADMIN for user in admins)
        # Проверяем сортировку по username
        assert admins[0].username == "admin1"
        assert admins[1].username == "admin2"

        # Тест 2: Получение всех обычных пользователей
        users = get_users_by_role(db_session, UserRole.USER)
        assert len(users) == 3
        assert all(user.role == UserRole.USER for user in users)
        # Проверяем сортировку по username
        assert users[0].username == "user1"
        assert users[1].username == "user2"
        assert users[2].username == "user3"

    def test_change_user_role_function(self, db_session: Session):
        """Тест функции change_user_role"""
        from crud.user import change_user_role, create_user, get_user
        from schemas.user import UserCreate
        from models.user import UserRole
        user_data = {
            "username": "user_to_promote",
            "full_name": "User To Promote",
            "role": UserRole.USER
        }
        created_user = create_user(db_session, UserCreate(**user_data))
        assert created_user.role == UserRole.USER

        updated_user = change_user_role(db_session, created_user.id, UserRole.ADMIN)
        assert updated_user is not None
        assert updated_user.role == UserRole.ADMIN

        db_user = get_user(db_session, created_user.id)
        assert db_user.role == UserRole.ADMIN

        result = change_user_role(db_session, 99999, UserRole.ADMIN)
        assert result is None

    def test_search_users_function(self, db_session: Session):
        """Тест функции search_users"""
        from crud.user import search_users, create_user
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем пользователей для поиска
        users_data = [
            ("alice_wonder", "Alice Wonderland", UserRole.USER),
            ("wonder_bob", "Bob Wonder", UserRole.USER),
            ("charlie_brown", "Charlie Brown", UserRole.USER),
            ("david_smith", "David Smith", UserRole.USER),
            ("emma_johnson", "Emma Johnson", UserRole.USER),
        ]

        for username, full_name, role in users_data:
            user_data = {"username": username, "full_name": full_name, "role": role}
            create_user(db_session, UserCreate(**user_data))

        wonder_users = search_users(db_session, "wonder")
        assert len(wonder_users) == 2

        limited_users = search_users(db_session, "o", limit=2)
        assert len(limited_users) == 2

        no_users = search_users(db_session, "xyz")
        assert len(no_users) == 0

        alice_users = search_users(db_session, "alice")
        assert len(alice_users) == 1
        assert alice_users[0].username == "alice_wonder"