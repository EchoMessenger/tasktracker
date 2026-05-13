import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime

from auth.dependencies import get_current_user_id
from main import app
from models.user import UserRole
from models.task import TaskDB, TaskStatus, TaskAssignmentDB
from schemas.task import TaskCreate
from schemas.user import UserCreate
from crud.user import create_user as crud_create_user
from crud.task import create_task as crud_create_task, get_task, task_to_dict


@pytest.fixture
def client():
    """Фикстура для тестового клиента"""
    with TestClient(app) as test_client:
        yield test_client



@pytest.fixture
def sample_task(db_session: Session, sample_user):
    """Создание тестовой задачи"""
    task = TaskDB(
        title="Test Task for Endpoint Tests",
        description="Test Description for Endpoint Tests",
        creator_id=sample_user.id,
        status=TaskStatus.OPEN
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    assignment = TaskAssignmentDB(
        task_id=task.id,
        user_id=sample_user.id
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(task)

    return task


def test_read_tasks_basic(client, sample_task):
    """Базовый тест получения задач"""
    response = client.get("/v2/tasks/")
    print(f"\nGET /v2/tasks/ - Status: {response.status_code}")

    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "data" in data
    assert "pagination" in data
    assert data["message"] == "Tasks retrieved successfully"



def test_create_task_user_not_found(client):
    """Создание задачи с несуществующим пользователем"""
    task_data = {
        "title": "Task with Invalid User",
        "description": "Should fail",
        "creator_id": 999999,
        "assigned_user_ids": []
    }

    response = client.post("/v2/tasks/", json=task_data)
    assert response.status_code == 404
    assert "Creator user with id 999999 not found" in response.json()["detail"]


def test_create_task_validation_error(client, sample_user):
    """Создание задачи с невалидными данными"""
    task_data = {
        "title": "",
        "description": "Test",
        "creator_id": sample_user.id,
        "assigned_user_ids": []
    }

    response = client.post("/v2/tasks/", json=task_data)
    assert response.status_code == 422


def test_get_task_by_id_success(client, db_session: Session, sample_user):
    """Успешное получение задачи по ID"""
    unique_id = str(uuid.uuid4())[:8]

    task = TaskDB(
        title=f"Get Test Task {unique_id}",
        description=f"Task for get by ID test {unique_id}",
        creator_id=sample_user.id,
        status=TaskStatus.OPEN,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    assignment = TaskAssignmentDB(task_id=task.id, user_id=sample_user.id)
    db_session.add(assignment)
    db_session.commit()

    response = client.get(f"/v2/tasks/{task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Task retrieved successfully"
    assert data["data"]["id"] == task.id
    assert data["data"]["title"] == f"Get Test Task {unique_id}"


def test_get_task_not_found(client):
    """Получение несуществующей задачи"""
    response = client.get("/v2/tasks/999999")
    assert response.status_code == 404
    assert "Task not found" in response.json()["detail"]


def test_update_task_status_success(client, db_session: Session, sample_user):
    task = TaskDB(
        title="Task for Status Update",
        description="Will update status",
        creator_id=sample_user.id,
        status=TaskStatus.OPEN
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    assignment = TaskAssignmentDB(task_id=task.id, user_id=sample_user.id)
    db_session.add(assignment)
    db_session.commit()

    task_id = task.id

    response = client.patch(
        f"/v2/tasks/{task_id}/status",
        json={"status": "in_progress"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Task status updated successfully"
    assert data["data"]["status"] == "in_progress"


def test_delete_task_success(client, db_session: Session, sample_user):
    """Успешное удаление задачи"""
    task = TaskDB(
        title="Task to Delete",
        description="Will be deleted",
        creator_id=sample_user.id,
        status=TaskStatus.OPEN
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    task_id = task.id

    response = client.delete(f"/v2/tasks/{task_id}")
    print(f"\nDELETE /v2/tasks/{task_id} - Status: {response.status_code}")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Task deleted successfully"

    response_check = client.get(f"/v2/tasks/{task_id}")
    assert response_check.status_code == 404

def test_create_task_forbidden(client, db_session):
    user = crud_create_user(db_session, UserCreate(
        username="no_create_user",
        full_name="No Create",
        role=UserRole.USER
    ))

    user.can_create_task = lambda: False

    response = client.post("/v2/tasks/", json={
        "title": "Forbidden Task",
        "description": "x",
        "creator_id": user.id,
        "assigned_user_ids": []
    })

    assert response.status_code == 403

def test_create_subtask_parent_not_found(client, sample_user):
    response = client.post(
        "/v2/tasks/99999/subtasks",
        json={
            "title": "Child",
            "description": "c",
            "creator_id": sample_user.id,
            "assigned_user_ids": []
        }
    )

    assert response.status_code == 404

def test_create_hierarchy_cycle(client, db_session, sample_user):
    t1 = crud_create_task(db_session, TaskCreate(
        title="T1", description="x",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))
    t2 = crud_create_task(db_session, TaskCreate(
        title="T2", description="x",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))

    client.post(f"/v2/tasks/hierarchy/{t1.id}/{t2.id}")
    response = client.post(f"/v2/tasks/hierarchy/{t2.id}/{t1.id}")

    assert response.status_code == 400

def test_delete_task_forbidden(client, db_session):
    creator = crud_create_user(db_session, UserCreate(
        username="creator_x",
        full_name="Creator X",
        role=UserRole.USER
    ))

    other = crud_create_user(db_session, UserCreate(
        username="other_x",
        full_name="Other X",
        role=UserRole.USER
    ))

    task = crud_create_task(db_session, TaskCreate(
        title="Task",
        description="x",
        creator_id=creator.id,
        assigned_user_ids=[]
    ))

    app.dependency_overrides[get_current_user_id] = lambda: other.id

    response = client.delete(f"/v2/tasks/{task.id}")

    assert response.status_code == 403

def test_assign_user_not_found(client, db_session, sample_user):
    task = crud_create_task(db_session, TaskCreate(
        title="Assign Test",
        description="x",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))

    response = client.post(
        f"/v2/tasks/{task.id}/assign",
        json=[99999]
    )

    assert response.status_code == 404

def test_update_task_status_cascade_to_parent(client, db_session: Session, sample_user):
    from crud.task import create_task_hierarchy
    from schemas.task import TaskCreate

    parent = crud_create_task(db_session, TaskCreate(
        title="Parent Task",
        description="Parent",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))

    child1 = crud_create_task(db_session, TaskCreate(
        title="Child 1",
        description="Child",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))

    child2 = crud_create_task(db_session, TaskCreate(
        title="Child 2",
        description="Child",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))

    create_task_hierarchy(db_session, parent.id, child1.id)
    create_task_hierarchy(db_session, parent.id, child2.id)

    response1 = client.patch(
        f"/v2/tasks/{child1.id}/status",
        json={"status": "completed"}
    )
    assert response1.status_code == 200

    parent_after_first = get_task(db_session, parent.id)
    assert parent_after_first.status == TaskStatus.OPEN

    response2 = client.patch(
        f"/v2/tasks/{child2.id}/status",
        json={"status": "completed"}
    )
    assert response2.status_code == 200

    parent_after_second = get_task(db_session, parent.id)
    assert parent_after_second.status == TaskStatus.COMPLETED

def test_update_status_completed_without_parent(client, db_session, sample_user):
    task = crud_create_task(db_session, TaskCreate(
        title="Single Task",
        description="No parent",
        creator_id=sample_user.id,
        assigned_user_ids=[]
    ))

    response = client.patch(
        f"/v2/tasks/{task.id}/status",
        json={"status": "completed"}
    )

    assert response.status_code == 200

def test_create_subtask_inherits_parent_assignments(client, db_session: Session, sample_user):
    from crud.task import get_task
    from models.task import TaskAssignmentDB, TaskHierarchyDB
    from schemas.task import TaskCreate
    from schemas.user import UserCreate

    user2 = crud_create_user(db_session, UserCreate(
        username="parent_assignee",
        full_name="Parent Assignee",
        role=UserRole.USER
    ))

    parent = crud_create_task(db_session, TaskCreate(
        title="Parent Task",
        description="Parent",
        creator_id=sample_user.id,
        assigned_user_ids=[sample_user.id, user2.id]
    ))

    response = client.post(
        f"/v2/tasks/{parent.id}/subtasks",
        json={
            "title": "Subtask",
            "description": "Child",
            "creator_id": sample_user.id,
            "assigned_user_ids": []
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Subtask created successfully"

    subtask_id = data["data"]["id"]

    assignments = db_session.query(TaskAssignmentDB).filter(
        TaskAssignmentDB.task_id == subtask_id
    ).all()

    assigned_user_ids = sorted([a.user_id for a in assignments])
    assert assigned_user_ids == sorted([sample_user.id, user2.id])

    hierarchy = db_session.query(TaskHierarchyDB).filter(
        TaskHierarchyDB.child_id == subtask_id
    ).first()

    assert hierarchy is not None
    assert hierarchy.parent_id == parent.id

    db_subtask = get_task(db_session, subtask_id)
    assert db_subtask is not None

def test_assign_users_to_task_success(client, db_session: Session, sample_user):
    """Успешное назначение пользователей на задачу"""
    task = TaskDB(
        title="Task for User Assignment",
        description="Will assign users",
        creator_id=sample_user.id,
        status=TaskStatus.OPEN
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    user2_data = UserCreate(
        username="user2_for_assign",
        full_name="User Two For Assign",
        role=UserRole.USER
    )
    user2 = crud_create_user(db_session, user2_data)

    response = client.post(
        f"/v2/tasks/{task.id}/assign",
        json=[sample_user.id, user2.id]
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Users assigned to task successfully"
    assert sample_user.id in data["data"]["assigned_user_ids"]
    assert user2.id in data["data"]["assigned_user_ids"]


def test_get_user_tasks_success(client, db_session: Session, sample_user):
    """Успешное получение задач пользователя"""
    base_id = str(uuid.uuid4())[:8]

    for i in range(2):
        task = TaskDB(
            title=f"User Task {i} {base_id}",
            description=f"Task {i} for user tests {base_id}",
            creator_id=sample_user.id,
            status=TaskStatus.OPEN,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        assignment = TaskAssignmentDB(task_id=task.id, user_id=sample_user.id)
        db_session.add(assignment)

    db_session.commit()

    response = client.get(f"/v2/tasks/user/{sample_user.id}/tasks")

    assert response.status_code == 200
    data = response.json()
    assert f"Tasks for user {sample_user.id} retrieved successfully" in data["message"]
    assert len(data["data"]) >= 1


def test_get_user_tasks_not_found(client):
    """Получение задач несуществующего пользователя"""
    response = client.get("/v2/tasks/user/999999/tasks")
    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


def test_get_task_stats_success(client):
    """Успешное получение статистики"""
    response = client.get("/v2/tasks/stats/overview")

    assert response.status_code == 200
    data = response.json()
    assert "Task statistics retrieved successfully" in data["message"]
    stats = data["data"]
    assert "total" in stats
    assert "open" in stats
    assert "in_progress" in stats
    assert "review" in stats
    assert "completed" in stats


def test_get_task_stats_with_user_id(client, sample_user):
    """Получение статистики по конкретному пользователю"""
    response = client.get(f"/v2/tasks/stats/overview?user_id={sample_user.id}")
    assert response.status_code == 200


def test_pagination_validation(client):
    """Тест валидации параметров пагинации"""
    assert client.get("/v2/tasks/?skip=0&limit=10").status_code == 200
    assert client.get("/v2/tasks/?skip=-1&limit=10").status_code == 422
    assert client.get("/v2/tasks/?skip=0&limit=0").status_code == 422
    assert client.get("/v2/tasks/?skip=0&limit=1001").status_code == 422


def test_filter_tasks_by_status(client):
    """Тест фильтрации задач по статусу"""
    for status in ["open", "in_progress", "review", "completed"]:
        response = client.get(f"/v2/tasks/?status={status}")
        assert response.status_code == 200
        for task in response.json()["data"]:
            assert task["status"] == status


def test_filter_tasks_by_user_id(client, sample_user):
    """Тест фильтрации задач по ID пользователя"""
    response = client.get(f"/v2/tasks/?user_id={sample_user.id}")
    assert response.status_code == 200


def test_search_tasks(client):
    """Тест поиска задач"""
    response = client.get("/v2/tasks/?search=test")
    assert response.status_code == 200


class TestTaskHierarchy:
    """Тесты для иерархии задач"""

    def test_create_hierarchy_success(self, client, db_session: Session, sample_user):
        """Тест создания иерархии"""
        task1 = TaskDB(
            title="Task 1",
            description="First task",
            creator_id=sample_user.id,
            status=TaskStatus.OPEN
        )
        task2 = TaskDB(
            title="Task 2",
            description="Second task",
            creator_id=sample_user.id,
            status=TaskStatus.OPEN
        )

        db_session.add_all([task1, task2])
        db_session.commit()
        db_session.refresh(task1)
        db_session.refresh(task2)

        response = client.post(f"/v2/tasks/hierarchy/{task1.id}/{task2.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Task hierarchy created successfully"

    def test_get_hierarchy_success(self, client, sample_task):
        """Тест получения иерархии"""
        response = client.get(f"/v2/tasks/{sample_task.id}/hierarchy")

        assert response.status_code == 200
        data = response.json()
        assert "Task hierarchy retrieved successfully" in data["message"]
        assert "task" in data["data"]
        assert "parents" in data["data"]
        assert "children" in data["data"]