import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text


class TestSimpleTaskCRUD:
    """Простые тесты для модуля задач"""

    def test_import_modules(self):
        """Тест что можем импортировать все необходимые модули"""
        from crud.task import get_task, task_to_dict
        from schemas.task import TaskCreate, TaskUpdate
        from models.task import TaskDB, TaskHierarchyDB, TaskAssignmentDB, TaskStatus
        assert True  # Все импорты успешны

    def test_task_tables_created(self, db_session: Session):
        """Тест что таблицы задач созданы"""
        from sqlalchemy import inspect

        inspector = inspect(db_session.get_bind())
        tables = inspector.get_table_names()

        # Проверяем основные таблицы
        assert 'tasks' in tables, "Таблица 'tasks' не создана"
        assert 'task_hierarchy' in tables, "Таблица 'task_hierarchy' не создана"
        assert 'task_assignments' in tables, "Таблица 'task_assignments' не создана"

        # Проверяем колонки таблицы tasks
        task_columns = inspector.get_columns('tasks')
        task_column_names = [col['name'] for col in task_columns]
        expected_task_columns = [
            'id', 'title', 'description', 'created_at', 'updated_at',
            'due_date', 'status', 'creator_id'
        ]

        for col in expected_task_columns:
            assert col in task_column_names, f"Колонка '{col}' отсутствует в таблице tasks"


class TestTaskFunctions:
    """Тесты для функций из crud/task.py"""

    def test_get_task_function(self, db_session: Session):
        """Тест функции get_task"""
        from crud.task import get_task
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        # Создаем пользователя
        user_data = {
            "username": "test_task_user",
            "full_name": "Test Task User",
            "role": UserRole.USER
        }
        created_user = create_user(db_session, UserCreate(**user_data))

        # Создаем задачу напрямую в БД
        db_task = TaskDB(
            title="Test Task",
            description="Test Description",
            creator_id=created_user.id,
            status=TaskStatus.OPEN
        )
        db_session.add(db_task)
        db_session.commit()
        db_session.refresh(db_task)

        # Получаем задачу через функцию get_task
        result = get_task(db_session, db_task.id)
        assert result is not None
        assert result.id == db_task.id
        assert result.title == "Test Task"
        assert result.description == "Test Description"
        assert result.status == TaskStatus.OPEN
        assert result.creator_id == created_user.id

        # Проверяем что функции joinedload работают
        assert result.creator is not None
        assert result.creator.username == "test_task_user"
        assert result.assignments is not None

        # Проверяем несуществующую задачу
        result = get_task(db_session, 99999)
        assert result is None

    def test_get_task_with_assignments(self, db_session: Session):
        """Тест получения задачи с назначенными пользователями"""
        from crud.task import get_task
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskAssignmentDB, TaskStatus
        from models.user import UserRole

        # Создаем пользователей
        creator = create_user(db_session, UserCreate(
            username="task_creator",
            full_name="Task Creator",
            role=UserRole.USER
        ))

        assignee1 = create_user(db_session, UserCreate(
            username="assignee1",
            full_name="Assignee One",
            role=UserRole.USER
        ))

        assignee2 = create_user(db_session, UserCreate(
            username="assignee2",
            full_name="Assignee Two",
            role=UserRole.USER
        ))

        # Создаем задачу
        db_task = TaskDB(
            title="Task with Assignments",
            description="Task with multiple assignments",
            creator_id=creator.id,
            status=TaskStatus.IN_PROGRESS
        )
        db_session.add(db_task)
        db_session.commit()
        db_session.refresh(db_task)

        # Создаем назначения
        assignment1 = TaskAssignmentDB(
            task_id=db_task.id,
            user_id=assignee1.id
        )
        assignment2 = TaskAssignmentDB(
            task_id=db_task.id,
            user_id=assignee2.id
        )
        db_session.add_all([assignment1, assignment2])
        db_session.commit()

        # Получаем задачу
        result = get_task(db_session, db_task.id)

        # Проверяем результат
        assert result is not None
        assert len(result.assignments) == 2
        assert result.assigned_user_ids == [assignee1.id, assignee2.id]

        # Проверяем загрузку связанных данных
        assert result.assignments[0].user is not None
        assert result.assignments[0].user.username == "assignee1"
        assert result.assignments[1].user is not None
        assert result.assignments[1].user.username == "assignee2"

    def test_get_task_with_hierarchy(self, db_session: Session):
        """Тест получения задачи с иерархическими связями"""
        from crud.task import get_task
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskHierarchyDB, TaskStatus
        from models.user import UserRole

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="hierarchy_user",
            full_name="Hierarchy User",
            role=UserRole.USER
        ))

        # Создаем задачи
        parent_task = TaskDB(
            title="Parent Task",
            description="Parent Description",
            creator_id=creator.id,
            status=TaskStatus.OPEN
        )

        child_task = TaskDB(
            title="Child Task",
            description="Child Description",
            creator_id=creator.id,
            status=TaskStatus.OPEN
        )

        db_session.add_all([parent_task, child_task])
        db_session.commit()
        db_session.refresh(parent_task)
        db_session.refresh(child_task)

        # Создаем иерархию
        hierarchy = TaskHierarchyDB(
            parent_id=parent_task.id,
            child_id=child_task.id
        )
        db_session.add(hierarchy)
        db_session.commit()

        # Получаем родительскую задачу
        parent_result = get_task(db_session, parent_task.id)
        assert parent_result is not None
        assert len(parent_result.child_relations) == 1
        assert parent_result.child_relations[0].child_id == child_task.id
        assert parent_result.child_relations[0].child_task is not None
        assert parent_result.child_relations[0].child_task.title == "Child Task"

        # Получаем дочернюю задачу
        child_result = get_task(db_session, child_task.id)
        assert child_result is not None
        assert len(child_result.parent_relations) == 1
        assert child_result.parent_relations[0].parent_id == parent_task.id
        assert child_result.parent_relations[0].parent_task is not None
        assert child_result.parent_relations[0].parent_task.title == "Parent Task"

    def test_task_to_dict_function(self, db_session: Session):
        """Тест функции task_to_dict"""
        from crud.task import get_task, task_to_dict
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskAssignmentDB, TaskStatus
        from models.user import UserRole

        # Создаем пользователей
        creator = create_user(db_session, UserCreate(
            username="dict_creator",
            full_name="Dict Creator",
            role=UserRole.ADMIN
        ))

        assignee = create_user(db_session, UserCreate(
            username="dict_assignee",
            full_name="Dict Assignee",
            role=UserRole.USER
        ))

        # Создаем задачу
        db_task = TaskDB(
            title="Task for Dict",
            description="Task for dictionary conversion",
            creator_id=creator.id,
            status=TaskStatus.COMPLETED
        )
        db_session.add(db_task)
        db_session.commit()
        db_session.refresh(db_task)

        # Добавляем назначение
        assignment = TaskAssignmentDB(
            task_id=db_task.id,
            user_id=assignee.id
        )
        db_session.add(assignment)
        db_session.commit()

        # Получаем задачу и преобразуем в словарь
        task = get_task(db_session, db_task.id)
        result_dict = task_to_dict(task)

        # Проверяем базовые поля
        assert result_dict["id"] == db_task.id
        assert result_dict["title"] == "Task for Dict"
        assert result_dict["description"] == "Task for dictionary conversion"
        assert result_dict["status"] == "completed"
        assert result_dict["creator_id"] == creator.id

        # Проверяем создателя
        assert result_dict["creator"] is not None
        assert result_dict["creator"]["id"] == creator.id
        assert result_dict["creator"]["username"] == "dict_creator"
        assert result_dict["creator"]["full_name"] == "Dict Creator"
        assert result_dict["creator"]["role"] == "admin"

        # Проверяем назначенных пользователей
        assert len(result_dict["assigned_users"]) == 1
        assert result_dict["assigned_users"][0]["id"] == assignee.id
        assert result_dict["assigned_users"][0]["username"] == "dict_assignee"
        assert result_dict["assigned_users"][0]["full_name"] == "Dict Assignee"
        assert result_dict["assigned_users"][0]["role"] == "user"

        # Проверяем assigned_user_ids
        assert result_dict["assigned_user_ids"] == [assignee.id]

        # Проверяем временные метки
        assert "created_at" in result_dict
        assert "updated_at" in result_dict

    def test_task_to_dict_without_assignments(self, db_session: Session):
        """Тест функции task_to_dict с задачей без назначений"""
        from crud.task import get_task, task_to_dict
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="no_assign_creator",
            full_name="No Assign Creator",
            role=UserRole.MANAGER
        ))

        # Создаем задачу без назначений
        db_task = TaskDB(
            title="Task Without Assignments",
            description="No assignments here",
            creator_id=creator.id,
            status=TaskStatus.REVIEW
        )
        db_session.add(db_task)
        db_session.commit()
        db_session.refresh(db_task)

        # Получаем задачу и преобразуем в словарь
        task = get_task(db_session, db_task.id)
        result_dict = task_to_dict(task)

        # Проверяем
        assert result_dict["id"] == db_task.id
        assert result_dict["title"] == "Task Without Assignments"
        assert result_dict["assigned_users"] == []  # Пустой список
        assert result_dict["assigned_user_ids"] == []  # Пустой список
        assert result_dict["creator"]["role"] == "manager"

    def test_task_to_dict_without_creator(self, db_session: Session):
        """Тест функции task_to_dict когда creator не загружен"""
        from crud.task import task_to_dict
        from models.task import TaskDB, TaskStatus

        # Создаем объект задачи напрямую (без загрузки creator)
        task = TaskDB(
            id=999,
            title="Standalone Task",
            description="No creator loaded",
            creator_id=1,  # ID существует, но creator не загружен
            status=TaskStatus.OPEN
        )

        # Преобразуем в словарь
        result_dict = task_to_dict(task)

        # Проверяем что creator=None когда не загружен
        assert result_dict["id"] == 999
        assert result_dict["title"] == "Standalone Task"
        assert result_dict["creator"] is None
        assert result_dict["assigned_users"] == []
        assert result_dict["assigned_user_ids"] == []

    def test_get_tasks_function_basic(self, db_session: Session):
        """Тест базовой функции get_tasks"""
        from crud.task import get_tasks
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="tasks_creator",
            full_name="Tasks Creator",
            role=UserRole.USER
        ))

        # Создаем несколько задач
        for i in range(1, 11):
            task = TaskDB(
                title=f"Task {i}",
                description=f"Description {i}",
                creator_id=creator.id,
                status=TaskStatus.OPEN
            )
            db_session.add(task)
        db_session.commit()

        # Получаем задачи с пагинацией
        tasks = get_tasks(db_session, skip=0, limit=5)
        assert len(tasks) == 5
        assert tasks[0].title == "Task 10"  # Сортировка по updated_at desc
        assert tasks[4].title == "Task 6"

        # Вторая страница
        tasks = get_tasks(db_session, skip=5, limit=5)
        assert len(tasks) == 5
        assert tasks[0].title == "Task 5"
        assert tasks[4].title == "Task 1"

        # Больше лимита
        tasks = get_tasks(db_session, skip=0, limit=20)
        assert len(tasks) == 10

    def test_get_tasks_with_user_filter(self, db_session: Session):
        """Тест get_tasks с фильтром по пользователю"""
        from crud.task import get_tasks
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskAssignmentDB, TaskStatus
        from models.user import UserRole

        # Создаем двух пользователей
        user1 = create_user(db_session, UserCreate(
            username="user1",
            full_name="User One",
            role=UserRole.USER
        ))

        user2 = create_user(db_session, UserCreate(
            username="user2",
            full_name="User Two",
            role=UserRole.USER
        ))

        # Создаем задачи для user1 (как создатель)
        for i in range(1, 4):
            task = TaskDB(
                title=f"User1 Task {i}",
                description=f"Created by user1",
                creator_id=user1.id,
                status=TaskStatus.OPEN
            )
            db_session.add(task)

        # Создаем задачи для user2 (как создатель)
        for i in range(1, 4):
            task = TaskDB(
                title=f"User2 Task {i}",
                description=f"Created by user2",
                creator_id=user2.id,
                status=TaskStatus.IN_PROGRESS
            )
            db_session.add(task)

        db_session.commit()

        # Назначаем одну задачу user2 на user1
        task_to_assign = db_session.query(TaskDB).filter(
            TaskDB.creator_id == user2.id
        ).first()

        if task_to_assign:
            assignment = TaskAssignmentDB(
                task_id=task_to_assign.id,
                user_id=user1.id
            )
            db_session.add(assignment)
            db_session.commit()

        # Получаем задачи для user1 (созданные + назначенные)
        user1_tasks = get_tasks(db_session, user_id=user1.id)
        assert len(user1_tasks) == 4  # 3 созданных + 1 назначенная

        # Получаем задачи для user2 (только созданные)
        user2_tasks = get_tasks(db_session, user_id=user2.id)
        assert len(user2_tasks) == 3

        # Проверяем что задачи принадлежат правильным пользователям
        user1_task_titles = [t.title for t in user1_tasks]
        assert "User1 Task 3" in user1_task_titles  # Одна из созданных
        assert task_to_assign.title in user1_task_titles  # Назначенная

    def test_get_tasks_with_status_filter(self, db_session: Session):
        """Тест get_tasks с фильтром по статусу"""
        from crud.task import get_tasks
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="status_filter_creator",
            full_name="Status Filter Creator",
            role=UserRole.USER
        ))

        # Создаем задачи с разными статусами
        status_counts = {
            TaskStatus.OPEN: 3,
            TaskStatus.IN_PROGRESS: 2,
            TaskStatus.REVIEW: 4,
            TaskStatus.COMPLETED: 1
        }

        for status, count in status_counts.items():
            for i in range(count):
                task = TaskDB(
                    title=f"{status.value} Task {i}",
                    description=f"{status.value} description",
                    creator_id=creator.id,
                    status=status
                )
                db_session.add(task)

        db_session.commit()

        # Фильтруем по статусу OPEN
        open_tasks = get_tasks(db_session, status="open")
        assert len(open_tasks) == 3
        assert all(task.status == TaskStatus.OPEN for task in open_tasks)

        # Фильтруем по статусу IN_PROGRESS
        in_progress_tasks = get_tasks(db_session, status="in_progress")
        assert len(in_progress_tasks) == 2
        assert all(task.status == TaskStatus.IN_PROGRESS for task in in_progress_tasks)

        # Фильтруем по статусу REVIEW
        review_tasks = get_tasks(db_session, status="review")
        assert len(review_tasks) == 4
        assert all(task.status == TaskStatus.REVIEW for task in review_tasks)

        # Фильтруем по статусу COMPLETED
        completed_tasks = get_tasks(db_session, status="completed")
        assert len(completed_tasks) == 1
        assert all(task.status == TaskStatus.COMPLETED for task in completed_tasks)

    def test_get_tasks_with_search_filter(self, db_session: Session):
        """Тест get_tasks с поисковым фильтром"""
        from crud.task import get_tasks
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="search_creator",
            full_name="Search Creator",
            role=UserRole.USER
        ))

        # Создаем задачи с разными названиями и описаниями
        tasks_data = [
            ("Project Alpha", "Important project about AI"),
            ("Beta Testing", "Testing phase for project"),
            ("Gamma Release", "Final release of gamma"),
            ("Alpha Version", "First version of alpha"),
            ("Beta Features", "New features for beta"),
            ("Documentation", "Project documentation")
        ]

        for title, description in tasks_data:
            task = TaskDB(
                title=title,
                description=description,
                creator_id=creator.id,
                status=TaskStatus.OPEN
            )
            db_session.add(task)

        db_session.commit()

        # Поиск по заголовку
        alpha_tasks = get_tasks(db_session, search="alpha")
        assert len(alpha_tasks) == 2
        titles = [t.title for t in alpha_tasks]
        assert "Project Alpha" in titles
        assert "Alpha Version" in titles

        # Поиск по описанию
        project_tasks = get_tasks(db_session, search="project")
        assert len(project_tasks) == 3  # "Project Alpha", "Beta Testing", "Project documentation"

        # Поиск по заголовку и описанию (регистр не важен)
        beta_tasks = get_tasks(db_session, search="BETA")
        assert len(beta_tasks) == 2
        assert "Beta Testing" in [t.title for t in beta_tasks]
        assert "Beta Features" in [t.title for t in beta_tasks]

        # Поиск который ничего не находит
        no_tasks = get_tasks(db_session, search="nonexistent")
        assert len(no_tasks) == 0

    def test_get_tasks_with_combined_filters(self, db_session: Session):
        """Тест get_tasks с комбинированными фильтрами"""
        from crud.task import get_tasks
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        # Создаем двух пользователей
        user1 = create_user(db_session, UserCreate(
            username="combined_user1",
            full_name="Combined User One",
            role=UserRole.USER
        ))

        user2 = create_user(db_session, UserCreate(
            username="combined_user2",
            full_name="Combined User Two",
            role=UserRole.USER
        ))

        # Создаем задачи для user1
        user1_tasks = [
            ("User1 Bug Fix", "Fix critical bug", TaskStatus.OPEN),
            ("User1 Feature", "New feature implementation", TaskStatus.IN_PROGRESS),
            ("User1 Review", "Code review needed", TaskStatus.REVIEW),
            ("User1 Completed", "Task completed", TaskStatus.COMPLETED),
        ]

        for title, description, status in user1_tasks:
            task = TaskDB(
                title=title,
                description=description,
                creator_id=user1.id,
                status=status
            )
            db_session.add(task)

        # Создаем задачи для user2
        user2_tasks = [
            ("User2 Bug Fix", "Fix minor bug", TaskStatus.OPEN),
            ("User2 Feature", "Another feature", TaskStatus.IN_PROGRESS),
        ]

        for title, description, status in user2_tasks:
            task = TaskDB(
                title=title,
                description=description,
                creator_id=user2.id,
                status=status
            )
            db_session.add(task)

        db_session.commit()

        # Комбинированный фильтр: user1 + статус OPEN
        user1_open_tasks = get_tasks(db_session, user_id=user1.id, status="open")
        assert len(user1_open_tasks) == 1
        assert user1_open_tasks[0].title == "User1 Bug Fix"
        assert user1_open_tasks[0].status == TaskStatus.OPEN

        # Комбинированный фильтр: user1 + поиск "feature"
        user1_feature_tasks = get_tasks(db_session, user_id=user1.id, search="feature")
        assert len(user1_feature_tasks) == 1
        assert user1_feature_tasks[0].title == "User1 Feature"

        # Комбинированный фильтр: user2 + статус IN_PROGRESS
        user2_in_progress = get_tasks(db_session, user_id=user2.id, status="in_progress")
        assert len(user2_in_progress) == 1
        assert user2_in_progress[0].title == "User2 Feature"

    def test_get_tasks_without_assignments(self, db_session: Session):
        """Тест get_tasks с include_assignments=False"""
        from crud.task import get_tasks
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="no_assign_loader",
            full_name="No Assign Loader",
            role=UserRole.USER
        ))

        task = TaskDB(
            title="Test without assignments loading",
            description="Test",
            creator_id=creator.id,
            status=TaskStatus.OPEN
        )
        db_session.add(task)
        db_session.commit()

        # Получаем без загрузки assignments
        tasks = get_tasks(db_session, include_assignments=False)
        assert len(tasks) >= 1
        # Проверяем что assignments не загружены (это сложно проверить напрямую,
        # но если не будет ошибок - значит работает)

    def test_get_tasks_count_function(self, db_session: Session):
        """Тест функции get_tasks_count"""
        from crud.task import get_tasks_count
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        # Создаем двух пользователей
        user1 = create_user(db_session, UserCreate(
            username="count_user1",
            full_name="Count User One",
            role=UserRole.USER
        ))

        user2 = create_user(db_session, UserCreate(
            username="count_user2",
            full_name="Count User Two",
            role=UserRole.USER
        ))

        # Создаем задачи для user1
        for i in range(5):
            task = TaskDB(
                title=f"User1 Task {i}",
                description="Task",
                creator_id=user1.id,
                status=TaskStatus.OPEN if i < 3 else TaskStatus.COMPLETED
            )
            db_session.add(task)

        # Создаем задачи для user2
        for i in range(3):
            task = TaskDB(
                title=f"User2 Task {i}",
                description="Task",
                creator_id=user2.id,
                status=TaskStatus.IN_PROGRESS
            )
            db_session.add(task)

        db_session.commit()

        # Общее количество задач
        total_count = get_tasks_count(db_session)
        assert total_count == 8

        # Количество задач для user1
        user1_count = get_tasks_count(db_session, user_id=user1.id)
        assert user1_count == 5

        # Количество задач с фильтром по статусу
        open_count = get_tasks_count(db_session, status="open")
        assert open_count == 3

        completed_count = get_tasks_count(db_session, status="completed")
        assert completed_count == 2

        in_progress_count = get_tasks_count(db_session, status="in_progress")
        assert in_progress_count == 3

    def test_get_tasks_count_with_search(self, db_session: Session):
        """Тест get_tasks_count с поиском"""
        from crud.task import get_tasks_count
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="count_search_creator",
            full_name="Count Search Creator",
            role=UserRole.USER
        ))

        tasks_data = [
            ("API Development", "Develop REST API"),
            ("Database Design", "Design database schema"),
            ("API Documentation", "Document API endpoints"),
            ("UI Development", "Develop user interface"),
            ("API Testing", "Test API endpoints")
        ]

        for title, description in tasks_data:
            task = TaskDB(
                title=title,
                description=description,
                creator_id=creator.id,
                status=TaskStatus.OPEN
            )
            db_session.add(task)

        db_session.commit()

        # Поиск по "API"
        api_count = get_tasks_count(db_session, search="API")
        assert api_count == 3

        # Поиск по "Development" - ДОЛЖНО БЫТЬ 2, а не 3
        # "API Development" и "UI Development" содержат "Development" в названии
        dev_count = get_tasks_count(db_session, search="Development")
        assert dev_count == 2  # Исправлено с 3 на 2

        # Поиск по "Design"
        design_count = get_tasks_count(db_session, search="Design")
        assert design_count == 1

        # Поиск который ничего не находит
        no_count = get_tasks_count(db_session, search="nonexistent")
        assert no_count == 0

    def test_get_tasks_count_with_combined_filters(self, db_session: Session):
        """Тест get_tasks_count с комбинированными фильтрами"""
        from crud.task import get_tasks_count
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus
        from models.user import UserRole

        user1 = create_user(db_session, UserCreate(
            username="combined_count_user1",
            full_name="Combined Count User One",
            role=UserRole.USER
        ))

        user2 = create_user(db_session, UserCreate(
            username="combined_count_user2",
            full_name="Combined Count User Two",
            role=UserRole.USER
        ))

        # Создаем задачи для user1
        user1_tasks = [
            ("Bug Fix A", "Fix bug in module A", TaskStatus.OPEN),
            ("Bug Fix B", "Fix bug in module B", TaskStatus.IN_PROGRESS),
            ("Feature A", "Add new feature A", TaskStatus.OPEN),
            ("Feature B", "Add new feature B", TaskStatus.COMPLETED),
        ]

        for title, description, status in user1_tasks:
            task = TaskDB(
                title=title,
                description=description,
                creator_id=user1.id,
                status=status
            )
            db_session.add(task)

        # Создаем задачи для user2
        user2_tasks = [
            ("Bug Fix C", "Fix bug in module C", TaskStatus.OPEN),
            ("Feature C", "Add new feature C", TaskStatus.IN_PROGRESS),
        ]

        for title, description, status in user2_tasks:
            task = TaskDB(
                title=title,
                description=description,
                creator_id=user2.id,
                status=status
            )
            db_session.add(task)

        db_session.commit()

        # Комбинированные фильтры
        user1_bug_count = get_tasks_count(db_session, user_id=user1.id, search="bug")
        assert user1_bug_count == 2

        user1_open_count = get_tasks_count(db_session, user_id=user1.id, status="open")
        assert user1_open_count == 2

        user1_open_bug_count = get_tasks_count(
            db_session,
            user_id=user1.id,
            status="open",
            search="bug"
        )
        assert user1_open_bug_count == 1

    def test_create_task_function(self, db_session: Session):
        """Тест функции create_task"""
        from crud.task import create_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole
        import datetime

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="task_creator_user",
            full_name="Task Creator User",
            role=UserRole.USER
        ))

        # Создаем задачу через функцию create_task
        due_date = datetime.datetime.utcnow() + datetime.timedelta(days=5)
        task_data = TaskCreate(
            title="New Task",
            description="New task description",
            due_date=due_date,
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        result = create_task(db_session, task_data)

        # Проверяем результат
        assert result is not None
        assert result["title"] == "New Task"
        assert result["description"] == "New task description"
        assert result["status"] == "open"
        assert result["creator_id"] == creator.id
        assert result["due_date"].date() == due_date.date()
        assert result["creator"] is not None
        assert result["creator"]["username"] == "task_creator_user"
        assert result["assigned_users"] == []
        assert result["assigned_user_ids"] == []

    def test_create_task_with_assigned_users(self, db_session: Session):
        """Тест создания задачи с назначенными пользователями"""
        from crud.task import create_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем создателя и пользователей для назначения
        creator = create_user(db_session, UserCreate(
            username="creator_with_assignees",
            full_name="Creator With Assignees",
            role=UserRole.USER
        ))

        assignee1 = create_user(db_session, UserCreate(
            username="assignee_for_task1",
            full_name="Assignee One",
            role=UserRole.USER
        ))

        assignee2 = create_user(db_session, UserCreate(
            username="assignee_for_task2",
            full_name="Assignee Two",
            role=UserRole.MANAGER
        ))

        # Создаем задачу с назначенными пользователями
        task_data = TaskCreate(
            title="Task With Assignees",
            description="Task with multiple assignees",
            creator_id=creator.id,
            assigned_user_ids=[assignee1.id, assignee2.id]
        )

        result = create_task(db_session, task_data)

        # Проверяем результат
        assert result is not None
        assert result["title"] == "Task With Assignees"
        assert len(result["assigned_users"]) == 2
        assert result["assigned_user_ids"] == [assignee1.id, assignee2.id]

        # Проверяем что пользователи правильно назначены
        assigned_usernames = [user["username"] for user in result["assigned_users"]]
        assert "assignee_for_task1" in assigned_usernames
        assert "assignee_for_task2" in assigned_usernames

        # Проверяем роли назначенных пользователей
        for user in result["assigned_users"]:
            if user["username"] == "assignee_for_task2":
                assert user["role"] == "manager"

    def test_create_task_without_description(self, db_session: Session):
        """Тест создания задачи без описания"""
        from crud.task import create_task
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="no_desc_creator",
            full_name="No Description Creator",
            role=UserRole.USER
        ))

        # Создаем задачу без описания
        task_data = TaskCreate(
            title="Task Without Description",
            description=None,
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        result = create_task(db_session, task_data)

        assert result is not None
        assert result["title"] == "Task Without Description"
        assert result["description"] is None
        assert result["status"] == "open"

    def test_update_task_function_basic(self, db_session: Session):
        """Тест базового обновления задачи"""
        from crud.task import create_task, update_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate, TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole
        import datetime

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="update_creator",
            full_name="Update Creator",
            role=UserRole.USER
        ))

        # Создаем задачу
        original_due_date = datetime.datetime.utcnow() + datetime.timedelta(days=3)
        task_data = TaskCreate(
            title="Original Title",
            description="Original Description",
            due_date=original_due_date,
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Обновляем задачу
        new_due_date = datetime.datetime.utcnow() + datetime.timedelta(days=10)
        update_data = TaskUpdate(
            title="Updated Title",
            description="Updated Description",
            due_date=new_due_date,
            status="in_progress"
        )

        updated_task = update_task(db_session, task_id, update_data, creator.id)

        # Проверяем обновления
        assert updated_task is not None
        assert updated_task["id"] == task_id
        assert updated_task["title"] == "Updated Title"
        assert updated_task["description"] == "Updated Description"
        assert updated_task["status"] == "in_progress"
        assert updated_task["due_date"].date() == new_due_date.date()
        assert updated_task["creator_id"] == creator.id

        # Проверяем что дата обновления изменилась
        assert updated_task["updated_at"] != created_task["updated_at"]

    def test_update_task_partial_update(self, db_session: Session):
        """Тест частичного обновления задачи"""
        from crud.task import create_task, update_task
        from crud.user import create_user
        from schemas.task import TaskCreate, TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="partial_update_creator",
            full_name="Partial Update Creator",
            role=UserRole.USER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Original Task",
            description="Original Description",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Обновляем только заголовок
        update_data = TaskUpdate(title="New Title Only")
        updated_task = update_task(db_session, task_id, update_data, creator.id)

        assert updated_task is not None
        assert updated_task["title"] == "New Title Only"
        assert updated_task["description"] == "Original Description"  # Не изменилось
        assert updated_task["status"] == "open"  # Не изменилось

        # Обновляем только статус
        update_data = TaskUpdate(status="completed")
        updated_task = update_task(db_session, task_id, update_data, creator.id)

        assert updated_task is not None
        assert updated_task["title"] == "New Title Only"  # Не изменилось
        assert updated_task["status"] == "completed"

    def test_update_task_with_assigned_users(self, db_session: Session):
        """Тест обновления задачи с назначением пользователей"""
        from crud.task import create_task, update_task
        from crud.user import create_user
        from schemas.task import TaskCreate, TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем пользователей
        creator = create_user(db_session, UserCreate(
            username="assign_update_creator",
            full_name="Assign Update Creator",
            role=UserRole.USER
        ))

        assignee1 = create_user(db_session, UserCreate(
            username="original_assignee",
            full_name="Original Assignee",
            role=UserRole.USER
        ))

        assignee2 = create_user(db_session, UserCreate(
            username="new_assignee",
            full_name="New Assignee",
            role=UserRole.USER
        ))

        # Создаем задачу с одним назначенным пользователем
        task_data = TaskCreate(
            title="Task to Update Assignments",
            description="Task description",
            creator_id=creator.id,
            assigned_user_ids=[assignee1.id]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Проверяем исходные назначения
        assert created_task["assigned_user_ids"] == [assignee1.id]

        # Обновляем назначения
        update_data = TaskUpdate(assigned_user_ids=[assignee2.id])
        updated_task = update_task(db_session, task_id, update_data, creator.id)

        # Проверяем что назначения обновились
        assert updated_task is not None
        assert updated_task["assigned_user_ids"] == [assignee2.id]

    def test_update_task_permissions_creator(self, db_session: Session):
        """Тест прав доступа для обновления задачи (создатель)"""
        from crud.task import create_task, update_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate, TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем создателя задачи
        creator = create_user(db_session, UserCreate(
            username="task_owner",
            full_name="Task Owner",
            role=UserRole.USER
        ))

        # Создаем другого пользователя
        other_user = create_user(db_session, UserCreate(
            username="other_user",
            full_name="Other User",
            role=UserRole.USER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Task to Update",
            description="Description",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Создатель может обновлять задачу
        update_data = TaskUpdate(title="Updated by Creator")
        result = update_task(db_session, task_id, update_data, creator.id)
        assert result is not None

        # Другой пользователь не может обновлять задачу
        update_data = TaskUpdate(title="Updated by Other")
        result = update_task(db_session, task_id, update_data, other_user.id)
        assert result is None

    def test_update_task_permissions_admin(self, db_session: Session):
        """Тест прав доступа для обновления задачи (администратор)"""
        from crud.task import create_task, update_task
        from crud.user import create_user
        from schemas.task import TaskCreate, TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем обычного пользователя и администратора
        regular_user = create_user(db_session, UserCreate(
            username="regular_user",
            full_name="Regular User",
            role=UserRole.USER
        ))

        admin_user = create_user(db_session, UserCreate(
            username="admin_user",
            full_name="Admin User",
            role=UserRole.ADMIN
        ))

        # Создаем задачу от имени обычного пользователя
        task_data = TaskCreate(
            title="Regular User Task",
            description="Description",
            creator_id=regular_user.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Администратор может обновлять задачу
        update_data = TaskUpdate(title="Updated by Admin")
        result = update_task(db_session, task_id, update_data, admin_user.id)
        assert result is not None
        assert result["title"] == "Updated by Admin"

    def test_update_task_permissions_manager(self, db_session: Session):
        """Тест прав доступа для обновления задачи (менеджер)"""
        from crud.task import create_task, update_task
        from crud.user import create_user
        from schemas.task import TaskCreate, TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем пользователей
        regular_user = create_user(db_session, UserCreate(
            username="regular_for_manager",
            full_name="Regular User",
            role=UserRole.USER
        ))

        manager_user = create_user(db_session, UserCreate(
            username="manager_user",
            full_name="Manager User",
            role=UserRole.MANAGER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Task for Manager Test",
            description="Description",
            creator_id=regular_user.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Менеджер может обновлять задачу
        update_data = TaskUpdate(title="Updated by Manager")
        result = update_task(db_session, task_id, update_data, manager_user.id)
        assert result is not None
        assert result["title"] == "Updated by Manager"

    def test_update_nonexistent_task(self, db_session: Session):
        """Тест обновления несуществующей задачи"""
        from crud.task import update_task
        from crud.user import create_user
        from schemas.task import TaskUpdate
        from schemas.user import UserCreate
        from models.user import UserRole

        user = create_user(db_session, UserCreate(
            username="user_for_nonexistent",
            full_name="User",
            role=UserRole.USER
        ))

        update_data = TaskUpdate(title="Try to Update")
        result = update_task(db_session, 99999, update_data, user.id)
        assert result is None

    def test_update_task_status_function(self, db_session: Session):
        """Тест функции update_task_status"""
        from crud.task import create_task, update_task_status
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.task import TaskStatus
        from models.user import UserRole

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="status_update_creator",
            full_name="Status Update Creator",
            role=UserRole.USER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Task for Status Update",
            description="Description",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Создатель может обновить статус
        updated_task = update_task_status(db_session, task_id, TaskStatus.IN_PROGRESS, creator.id)
        assert updated_task is not None
        assert updated_task["status"] == "in_progress"

        # Обновляем еще раз
        updated_task = update_task_status(db_session, task_id, TaskStatus.COMPLETED, creator.id)
        assert updated_task is not None
        assert updated_task["status"] == "completed"

    def test_update_task_status_by_assigned_user(self, db_session: Session):
        """Тест обновления статуса задачи назначенным пользователем"""
        from crud.task import create_task, update_task_status
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.task import TaskStatus
        from models.user import UserRole

        # Создаем пользователей
        creator = create_user(db_session, UserCreate(
            username="status_creator",
            full_name="Status Creator",
            role=UserRole.USER
        ))

        assignee = create_user(db_session, UserCreate(
            username="status_assignee",
            full_name="Status Assignee",
            role=UserRole.USER
        ))

        # Создаем задачу и назначаем пользователя
        task_data = TaskCreate(
            title="Task for Assignee Status Update",
            description="Description",
            creator_id=creator.id,
            assigned_user_ids=[assignee.id]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Назначенный пользователь может обновить статус
        updated_task = update_task_status(db_session, task_id, TaskStatus.REVIEW, assignee.id)
        assert updated_task is not None
        assert updated_task["status"] == "review"

    def test_update_task_status_permission_denied(self, db_session: Session):
        """Тест отказа в доступе при обновлении статуса"""
        from crud.task import create_task, update_task_status
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.task import TaskStatus
        from models.user import UserRole

        # Создаем пользователей
        creator = create_user(db_session, UserCreate(
            username="permission_creator",
            full_name="Permission Creator",
            role=UserRole.USER
        ))

        assignee = create_user(db_session, UserCreate(
            username="permission_assignee",
            full_name="Permission Assignee",
            role=UserRole.USER
        ))

        other_user = create_user(db_session, UserCreate(
            username="other_user_no_access",
            full_name="Other User No Access",
            role=UserRole.USER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Task for Permission Test",
            description="Description",
            creator_id=creator.id,
            assigned_user_ids=[assignee.id]  # Назначаем только assignee
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Создатель может обновить статус
        result = update_task_status(db_session, task_id, TaskStatus.IN_PROGRESS, creator.id)
        assert result is not None

        # Назначенный пользователь может обновить статус
        result = update_task_status(db_session, task_id, TaskStatus.REVIEW, assignee.id)
        assert result is not None

        # Другой пользователь НЕ может обновить статус
        result = update_task_status(db_session, task_id, TaskStatus.COMPLETED, other_user.id)
        assert result is None

        # Проверяем что статус остался REVIEW
        from crud.task import get_task
        task = get_task(db_session, task_id)
        assert task.status == TaskStatus.REVIEW

    def test_update_task_status_nonexistent_task(self, db_session: Session):
        """Тест обновления статуса несуществующей задачи"""
        from crud.task import update_task_status
        from crud.user import create_user
        from schemas.user import UserCreate
        from models.task import TaskStatus
        from models.user import UserRole

        user = create_user(db_session, UserCreate(
            username="user_for_nonexistent_status",
            full_name="User",
            role=UserRole.USER
        ))

        result = update_task_status(db_session, 99999, TaskStatus.COMPLETED, user.id)
        assert result is None

    def test_delete_task_function(self, db_session: Session):
        """Тест функции delete_task"""
        from crud.task import create_task, delete_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="delete_creator",
            full_name="Delete Creator",
            role=UserRole.USER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Task to Delete",
            description="Will be deleted",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Проверяем что задача существует
        assert get_task(db_session, task_id) is not None

        # Удаляем задачу
        result = delete_task(db_session, task_id)
        assert result is True

        # Проверяем что задача удалена
        assert get_task(db_session, task_id) is None

    def test_delete_task_with_assignments(self, db_session: Session):
        """Тест удаления задачи с назначениями"""
        from crud.task import create_task, delete_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        # Создаем пользователей
        creator = create_user(db_session, UserCreate(
            username="delete_with_assign_creator",
            full_name="Delete With Assign Creator",
            role=UserRole.USER
        ))

        assignee = create_user(db_session, UserCreate(
            username="delete_assignee",
            full_name="Delete Assignee",
            role=UserRole.USER
        ))

        # Создаем задачу с назначением
        task_data = TaskCreate(
            title="Task with Assignment to Delete",
            description="Description",
            creator_id=creator.id,
            assigned_user_ids=[assignee.id]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Проверяем что задача существует
        assert get_task(db_session, task_id) is not None

        # Удаляем задачу
        result = delete_task(db_session, task_id)
        assert result is True

        # Проверяем что задача удалена
        assert get_task(db_session, task_id) is None

        # Проверяем что назначения тоже удалены
        from models.task import TaskAssignmentDB
        assignments = db_session.query(TaskAssignmentDB).filter(
            TaskAssignmentDB.task_id == task_id
        ).all()
        assert len(assignments) == 0

    def test_delete_task_with_hierarchy(self, db_session: Session):
        """Тест удаления задачи с иерархическими связями"""
        from crud.task import create_task, delete_task, get_task, create_task_hierarchy
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole
        from models.task import TaskDB, TaskHierarchyDB
        # Создаем пользователя
        creator = create_user(db_session, UserCreate(
            username="hierarchy_delete_creator",
            full_name="Hierarchy Delete Creator",
            role=UserRole.USER
        ))

        # Создаем две задачи
        task1_data = TaskCreate(
            title="Parent Task to Delete",
            description="Parent",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        task2_data = TaskCreate(
            title="Child Task",
            description="Child",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        task1 = create_task(db_session, task1_data)
        task2 = create_task(db_session, task2_data)

        # Создаем иерархическую связь
        hierarchy_result = create_task_hierarchy(db_session, task1["id"], task2["id"])
        assert hierarchy_result is not None

        # Проверяем что иерархия создана
        from models.task import TaskHierarchyDB
        hierarchies = db_session.query(TaskHierarchyDB).filter(
            TaskHierarchyDB.parent_id == task1["id"]
        ).all()
        assert len(hierarchies) == 1

        # Удаляем родительскую задачу (используем простой запрос для проверки)
        db_task = db_session.query(TaskDB).filter(TaskDB.id == task1["id"]).first()
        assert db_task is not None

        result = delete_task(db_session, task1["id"])
        assert result is True

        # Проверяем что задача удалена
        assert get_task(db_session, task1["id"]) is None

        # Проверяем что иерархические связи удалены
        hierarchies = db_session.query(TaskHierarchyDB).filter(
            TaskHierarchyDB.parent_id == task1["id"]
        ).all()
        assert len(hierarchies) == 0

        # Проверяем что дочерняя задача осталась
        assert get_task(db_session, task2["id"]) is not None

    def test_delete_nonexistent_task(self, db_session: Session):
        """Тест удаления несуществующей задачи"""
        from crud.task import delete_task

        result = delete_task(db_session, 99999)
        assert result is False

    def test_assign_users_to_task_function(self, db_session: Session):
        """Тест функции assign_users_to_task"""
        from crud.task import create_task, assign_users_to_task, get_task
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="assign_function_creator",
            full_name="Assign Function Creator",
            role=UserRole.USER
        ))

        assignee1 = create_user(db_session, UserCreate(
            username="assign_func_user1",
            full_name="Assign Func User1",
            role=UserRole.USER
        ))

        assignee2 = create_user(db_session, UserCreate(
            username="assign_func_user2",
            full_name="Assign Func User2",
            role=UserRole.USER
        ))

        # Создаем задачу
        task_data = TaskCreate(
            title="Task for Assign Function",
            description="Test",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        created_task = create_task(db_session, task_data)
        task_id = created_task["id"]

        # Назначаем пользователей
        result = assign_users_to_task(db_session, task_id, [assignee1.id, assignee2.id])
        assert result is True

        # Проверяем назначения
        task = get_task(db_session, task_id)
        assert set(task.assigned_user_ids) == {assignee1.id, assignee2.id}

        # Обновляем назначения (меняем список)
        result = assign_users_to_task(db_session, task_id, [assignee1.id])
        assert result is True

        task = get_task(db_session, task_id)
        assert task.assigned_user_ids == [assignee1.id]

    def test_get_user_tasks_function(self, db_session: Session):
        """Тест функции get_user_tasks"""
        from crud.task import create_task, get_user_tasks
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        user1 = create_user(db_session, UserCreate(
            username="user_tasks_1",
            full_name="User Tasks 1",
            role=UserRole.USER
        ))

        user2 = create_user(db_session, UserCreate(
            username="user_tasks_2",
            full_name="User Tasks 2",
            role=UserRole.USER
        ))

        # Создаем задачи для user1
        for i in range(3):
            task_data = TaskCreate(
                title=f"User1 Task {i}",
                description="Description",
                creator_id=user1.id,
                assigned_user_ids=[]
            )
            create_task(db_session, task_data)

        # Создаем задачу для user2 и назначаем на user1
        task_data = TaskCreate(
            title="User2 Task assigned to User1",
            description="Description",
            creator_id=user2.id,
            assigned_user_ids=[user1.id]
        )
        create_task(db_session, task_data)

        # Получаем задачи user1
        user1_tasks = get_user_tasks(db_session, user1.id)
        assert len(user1_tasks) == 4  # 3 созданных + 1 назначенная

    def test_get_task_stats_function(self, db_session: Session):
        """Тест функции get_task_stats"""
        from crud.task import create_task, get_task_stats
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.task import TaskDB, TaskStatus, TaskAssignmentDB
        from models.user import UserRole

        user = create_user(db_session, UserCreate(
            username="stats_user",
            full_name="Stats User",
            role=UserRole.USER
        ))

        # Создаем задачи с разными статусами
        status_counts = [
            (TaskStatus.OPEN, 2),
            (TaskStatus.IN_PROGRESS, 3),
            (TaskStatus.REVIEW, 1),
            (TaskStatus.COMPLETED, 1)
        ]

        for status, count in status_counts:
            for i in range(count):
                # Создаем задачу напрямую
                task = TaskDB(
                    title=f"{status.value} task {i}",
                    description="Description",
                    creator_id=user.id,
                    status=status
                )
                db_session.add(task)
                db_session.flush()  # Получаем ID задачи

                # Назначаем задачу на пользователя (чтобы JOIN сработал)
                assignment = TaskAssignmentDB(
                    task_id=task.id,
                    user_id=user.id
                )
                db_session.add(assignment)

        db_session.commit()

        # Получаем статистику
        stats = get_task_stats(db_session, user.id)

        # Проверяем статистику
        assert stats["total"] == 7
        assert stats["open"] == 2
        assert stats["in_progress"] == 3
        assert stats["review"] == 1
        assert stats["completed"] == 1

        # Тест статистики без user_id (общая статистика)
        all_stats = get_task_stats(db_session)
        # Проверяем что есть хотя бы какие-то данные
        assert "total" in all_stats

    def test_create_task_hierarchy_function(self, db_session: Session):
        """Тест функции create_task_hierarchy"""
        from crud.task import create_task, create_task_hierarchy
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="hierarchy_creator_func",
            full_name="Hierarchy Creator Func",
            role=UserRole.USER
        ))

        # Создаем две задачи
        parent_task_data = TaskCreate(
            title="Parent Task",
            description="Parent",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        child_task_data = TaskCreate(
            title="Child Task",
            description="Child",
            creator_id=creator.id,
            assigned_user_ids=[]
        )

        parent = create_task(db_session, parent_task_data)
        child = create_task(db_session, child_task_data)

        # Создаем иерархию
        hierarchy = create_task_hierarchy(db_session, parent["id"], child["id"])

        assert hierarchy is not None
        assert hierarchy["parent_id"] == parent["id"]
        assert hierarchy["child_id"] == child["id"]
        assert "created_at" in hierarchy

        # Пытаемся создать дубликат
        duplicate = create_task_hierarchy(db_session, parent["id"], child["id"])
        assert duplicate is not None  # Должен вернуть существующую

        # Пытаемся создать с несуществующими задачами
        invalid = create_task_hierarchy(db_session, 99999, child["id"])
        assert invalid is None

    def test_get_task_hierarchy_function(self, db_session: Session):
        """Тест функции get_task_hierarchy"""
        from crud.task import create_task, create_task_hierarchy, get_task_hierarchy
        from crud.user import create_user
        from schemas.task import TaskCreate
        from schemas.user import UserCreate
        from models.user import UserRole

        creator = create_user(db_session, UserCreate(
            username="get_hierarchy_creator",
            full_name="Get Hierarchy Creator",
            role=UserRole.USER
        ))

        # Создаем несколько задач
        tasks = []
        for i in range(3):
            task_data = TaskCreate(
                title=f"Task {i}",
                description=f"Task {i} description",
                creator_id=creator.id,
                assigned_user_ids=[]
            )
            tasks.append(create_task(db_session, task_data))

        # Создаем иерархию: Task0 -> Task1 -> Task2
        create_task_hierarchy(db_session, tasks[0]["id"], tasks[1]["id"])
        create_task_hierarchy(db_session, tasks[1]["id"], tasks[2]["id"])

        # Получаем иерархию для Task1 (посредник)
        hierarchy = get_task_hierarchy(db_session, tasks[1]["id"])

        assert hierarchy is not None
        assert "task" in hierarchy
        assert "parents" in hierarchy
        assert "children" in hierarchy

        # Task1 должен иметь Task0 как родителя
        assert len(hierarchy["parents"]) == 1
        assert hierarchy["parents"][0]["id"] == tasks[0]["id"]

        # Task1 должен иметь Task2 как ребенка
        assert len(hierarchy["children"]) == 1
        assert hierarchy["children"][0]["id"] == tasks[2]["id"]

        # Для Task0 не должно быть родителей
        hierarchy_task0 = get_task_hierarchy(db_session, tasks[0]["id"])
        assert len(hierarchy_task0["parents"]) == 0
        assert len(hierarchy_task0["children"]) == 1

        # Для несуществующей задачи
        invalid_hierarchy = get_task_hierarchy(db_session, 99999)
        assert invalid_hierarchy == {}