from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from auth import current_user_auth

from database import get_db
from models import UserDB, TaskDB
from models.task import TaskStatus
from schemas.task import TaskResponse, TaskCreate, TaskUpdate, TaskStatusUpdate  # Используем TaskResponse вместо Task
from schemas.response import StandardResponse, PaginatedResponse
import crud.task as task_crud
import crud.user as user_crud

router = APIRouter(prefix="/v2/tasks", tags=["tasks-v2"])


def get_current_user():
    """Заглушка - в реальном приложении здесь будет JWT токен"""
    return 2


@router.post("/", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
def create_task(
        task: TaskCreate,
        db: Session = Depends(get_db)
):
    """Создать новую задачу"""
    # Проверяем существование пользователя-создателя
    creator = user_crud.get_user(db, task.creator_id)
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator user with id {task.creator_id} not found"
        )
    if not creator.can_create_task():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User with role '{creator.role.value}' cannot create tasks"
        )

    # Проверяем существование назначенных пользователей
    if task.assigned_user_ids:
        for user_id in task.assigned_user_ids:
            if not user_crud.get_user(db, user_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User with id {user_id} not found"
                )

    task_created = task_crud.create_task(db=db, task=task)
    return StandardResponse(
        message="Task created successfully",
        data=task_created
    )


@router.post("/{parent_id}/subtasks", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
def create_subtask(
        parent_id: int,
        subtask: TaskCreate,
        db: Session = Depends(get_db)
):
    """Создать подзадачу для указанной родительской задачи"""
    creator = user_crud.get_user(db, subtask.creator_id)
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Creator user with id {subtask.creator_id} not found"
        )
    if not creator.can_create_task():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User with role '{creator.role.value}' cannot create tasks"
        )
    parent_task = task_crud.get_task(db, parent_id)
    if not parent_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent task with id {parent_id} not found"
        )
    parent_assigned_users = task_crud.get_assigned_users(db, parent_id)
    parent_user_ids = [user.id for user in parent_assigned_users]
    for user_id in parent_user_ids:
        if not user_crud.get_user(db, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} from parent task not found"
            )
    subtask_data = subtask.dict()
    subtask_data["parent_id"] = parent_id
    subtask_data["assigned_user_ids"] = parent_user_ids
    subtask_created = task_crud.create_task(db=db, task=TaskCreate(**subtask_data))
    hierarchy = task_crud.create_task_hierarchy(db, parent_id, subtask_created.id)
    if not hierarchy:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create task hierarchy - would create cycle or invalid relationship"
        )
    subtask_with_hierarchy = task_crud.get_task(db, subtask_created.id)

    return StandardResponse(
        message="Subtask created successfully",
        data=task_crud.task_to_dict(subtask_with_hierarchy) if subtask_with_hierarchy else subtask_created
    )

@router.get("/", response_model=PaginatedResponse[TaskResponse])
def read_tasks(
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
        user_id: Optional[int] = Query(None, description="Filter by user ID"),
        status: Optional[str] = Query(None, description="Filter by status"),
        search: Optional[str] = Query(None, description="Search in title and description"),
        db: Session = Depends(get_db)
):
    """Получить список задач с фильтрацией"""
    tasks = task_crud.get_tasks(
        db,
        skip=skip,
        limit=limit,
        user_id=user_id,
        status=status,
        search=search
    )
    total = task_crud.get_tasks_count(db, user_id=user_id, status=status, search=search)

    # Преобразуем задачи в словари
    tasks_dict = [task_crud.task_to_dict(task) for task in tasks]

    return PaginatedResponse(
        message="Tasks retrieved successfully",
        data=tasks_dict,
        pagination={
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    )


@router.get("/{task_id}", response_model=StandardResponse)
def read_task(task_id: int, db: Session = Depends(get_db)):
    """Получить задачу по ID"""
    db_task = task_crud.get_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    # Преобразуем в словарь для сериализации
    task_dict = task_crud.task_to_dict(db_task)

    return StandardResponse(
        message="Task retrieved successfully",
        data=task_dict
    )

@router.put("/{task_id}", response_model=StandardResponse)
def update_task(
        task_id: int,
        task: TaskUpdate,
        db: Session = Depends(get_db),
        current_user_id: int = Depends(get_current_user)
):
    """Обновить задачу"""
    db_task = task_crud.update_task(db, task_id=task_id, task_update=task, current_user_id=current_user_id)
    if db_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return StandardResponse(
        message="Task updated successfully",
        data=db_task
    )


@router.patch("/{task_id}/status", response_model=StandardResponse)
def update_task_status(
        task_id: int,
        status_update: TaskStatusUpdate,
        db: Session = Depends(get_db),
        current_user_id: int = Depends(get_current_user)
):
    """Обновить статус задачи с автоматическим обновлением родительской задачи"""
    db_task = task_crud.update_task_status(
        db,
        task_id=task_id,
        new_status=status_update.status,
        current_user_id=current_user_id
    )

    if db_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not enough permissions"
        )

    # Если задача переведена в статус "выполнено"
    if status_update.status == "completed":
        full_task = task_crud.get_task(db, task_id)

        if full_task and full_task.parent_id:
            child_tasks = db.query(TaskDB).filter(
                TaskDB.parent_id == full_task.parent_id
            ).all()
            all_children_completed = all(
                task.status == TaskStatus.COMPLETED for task in child_tasks
            )
            if all_children_completed:
                task_crud.update_task_status(
                    db,
                    task_id=full_task.parent_id,
                    new_status=TaskStatus.COMPLETED,
                    current_user_id=current_user_id
                )

    return StandardResponse(
        message="Task status updated successfully",
        data=db_task
    )


@router.delete("/{task_id}", response_model=StandardResponse)
def delete_task(
        task_id: int,
        db: Session = Depends(get_db),
        current_user_id: int = Depends(get_current_user)
):
    """Удалить задачу"""
    db_task = task_crud.get_task(db, task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    if db_task.creator_id != current_user_id:
        user = user_crud.get_user(db, current_user_id)
        if not user or not user.can_delete_tasks():
            raise HTTPException(status_code=403, detail="Not enough permissions")

    success = task_crud.delete_task(db, task_id=task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    return StandardResponse(
        message="Task deleted successfully",
        data=None
    )


@router.post("/{task_id}/assign", response_model=StandardResponse)
def assign_users_to_task(
        task_id: int,
        user_ids: List[int],
        db: Session = Depends(get_db)
):
    """Назначить пользователей на задачу"""
    task = task_crud.get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    for user_id in user_ids:
        if not user_crud.get_user(db, user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

    success = task_crud.assign_users_to_task(db, task_id, user_ids)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to assign users to task"
        )

    updated_task = task_crud.get_task(db, task_id)
    return StandardResponse(
        message="Users assigned to task successfully",
        data=task_crud.task_to_dict(updated_task)
    )


@router.get("/user/{user_id}/tasks",
            response_model=PaginatedResponse[TaskResponse])  # Исправлено: TaskResponse вместо Task
def get_user_tasks(
        user_id: int,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session = Depends(get_db)
):
    """Получить все задачи пользователя"""
    if not user_crud.get_user(db, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    tasks = task_crud.get_tasks(db, skip=skip, limit=limit, user_id=user_id)
    total = task_crud.get_tasks_count(db, user_id=user_id)

    return PaginatedResponse(
        message=f"Tasks for user {user_id} retrieved successfully",
        data=tasks,
        pagination={
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": (total + limit - 1) // limit if limit > 0 else 1
        }
    )


@router.get("/stats/overview", response_model=StandardResponse)
def get_tasks_stats(
        user_id: Optional[int] = Query(None, description="User ID for personal stats"),
        db: Session = Depends(get_db)
):
    """Получить статистику по задачам"""
    stats = task_crud.get_task_stats(db, user_id=user_id)
    return StandardResponse(
        message="Task statistics retrieved successfully",
        data=stats
    )


@router.post("/hierarchy/{parent_id}/{child_id}", response_model=StandardResponse)
def create_task_hierarchy(
        parent_id: int,
        child_id: int,
        db: Session = Depends(get_db)
):
    """Создать связь родитель-потомок между задачами"""
    hierarchy = task_crud.create_task_hierarchy(db, parent_id, child_id)
    if not hierarchy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create hierarchy - tasks not found or would create cycle"
        )

    return StandardResponse(
        message="Task hierarchy created successfully",
        data=hierarchy
    )


@router.get("/{task_id}/hierarchy", response_model=StandardResponse)
def get_task_hierarchy(task_id: int, db: Session = Depends(get_db)):
    """Получить иерархию задачи"""
    hierarchy = task_crud.get_task_hierarchy(db, task_id)
    if not hierarchy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    return StandardResponse(
        message="Task hierarchy retrieved successfully",
        data=hierarchy
    )