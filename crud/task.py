from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from typing import List, Optional
import datetime

from models.task import TaskDB, TaskHierarchyDB, TaskAssignmentDB, TaskStatus
from models.user import UserDB, UserRole
from schemas.task import TaskCreate, TaskUpdate


def get_task(db: Session, task_id: int) -> Optional[TaskDB]:
    """Получить задачу по ID со всеми связями"""
    task = db.query(TaskDB).options(
        joinedload(TaskDB.creator),
        joinedload(TaskDB.assignments).joinedload(TaskAssignmentDB.user),
        joinedload(TaskDB.parent_relations).joinedload(TaskHierarchyDB.parent_task),
        joinedload(TaskDB.child_relations).joinedload(TaskHierarchyDB.child_task)
    ).filter(TaskDB.id == task_id).first()

    if task:
        task.assigned_user_ids = [assignment.user_id for assignment in task.assignments]

    return task


def task_to_dict(task: TaskDB) -> dict:
    """Преобразовать объект TaskDB в словарь для сериализации"""
    creator_dict = None
    if task.creator:
        creator_dict = {
            "id": task.creator.id,
            "username": task.creator.username,
            "full_name": task.creator.full_name,
            "role": task.creator.role.value,
            "created_at": task.creator.created_at
        }
    assigned_users = []
    for assignment in task.assignments:
        if assignment.user:
            assigned_users.append({
                "id": assignment.user.id,
                "username": assignment.user.username,
                "full_name": assignment.user.full_name,
                "role": assignment.user.role.value,
                "created_at": assignment.user.created_at
            })

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date,
        "status": task.status.value,
        "creator_id": task.creator_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "creator": creator_dict,
        "assigned_users": assigned_users,
        "assigned_user_ids": [assignment.user_id for assignment in task.assignments]
    }


def get_tasks(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        include_assignments: bool = True
) -> List[TaskDB]:
    """Получить список задач с фильтрацией"""
    query = db.query(TaskDB).distinct()  # Добавить distinct
    if include_assignments:
        query = query.options(
            joinedload(TaskDB.creator),
            joinedload(TaskDB.assignments).joinedload(TaskAssignmentDB.user)
        )
    if user_id:
        from sqlalchemy import exists
        assignment_exists = exists().where(
            and_(
                TaskAssignmentDB.task_id == TaskDB.id,
                TaskAssignmentDB.user_id == user_id
            )
        )
        query = query.filter(
            or_(
                TaskDB.creator_id == user_id,
                assignment_exists
            )
        )
    if status:
        query = query.filter(TaskDB.status == TaskStatus(status))
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                TaskDB.title.ilike(search_filter),
                TaskDB.description.ilike(search_filter)
            )
        )

    return query.order_by(desc(TaskDB.updated_at)).offset(skip).limit(limit).all()


def get_tasks_count(
        db: Session,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
) -> int:
    """Получить общее количество задач для пагинации"""
    if user_id:
        from sqlalchemy import exists
        assignment_exists = exists().where(
            and_(
                TaskAssignmentDB.task_id == TaskDB.id,
                TaskAssignmentDB.user_id == user_id
            )
        )
        query = db.query(TaskDB).filter(
            or_(
                TaskDB.creator_id == user_id,
                assignment_exists
            )
        )
    else:
        query = db.query(TaskDB)
    if status:
        query = query.filter(TaskDB.status == TaskStatus(status))
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                TaskDB.title.ilike(search_filter),
                TaskDB.description.ilike(search_filter)
            )
        )
    return query.count()


def create_task(db: Session, task: TaskCreate) -> TaskDB:  # Убрали creator_id из параметров
    """Создать новую задачу"""
    db_task = TaskDB(
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        creator_id=task.creator_id,  # Берем из схемы task
        status=TaskStatus.OPEN
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    if task.assigned_user_ids:
        assign_users_to_task(db, db_task.id, task.assigned_user_ids)
    created_task = get_task(db, db_task.id)
    if created_task:
        return task_to_dict(created_task)
    return None


def update_task(db: Session, task_id: int, task_update: TaskUpdate, current_user_id: int) -> Optional[dict]:
    """Обновить задачу с проверкой прав"""
    db_task = get_task(db, task_id)
    if not db_task:
        return None
    if db_task.creator_id != current_user_id:
        user = db.query(UserDB).filter(UserDB.id == current_user_id).first()
        if not user or user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
            return None
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field != 'assigned_user_ids' and value is not None:
            setattr(db_task, field, value)
    if 'status' in update_data and update_data['status'] is not None:
        db_task.status = TaskStatus(update_data['status'])
    if 'assigned_user_ids' in update_data:
        assign_users_to_task(db, task_id, task_update.assigned_user_ids)
    db_task.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    return task_to_dict(db_task)


def update_task_status(db: Session, task_id: int, new_status: TaskStatus, current_user_id: int) -> Optional[TaskDB]:
    """Обновить статус задачи (могут создатель или назначенные)"""
    db_task = get_task(db, task_id)
    if not db_task:
        return None
    is_assigned = any(assignment.user_id == current_user_id for assignment in db_task.assignments)
    if db_task.creator_id != current_user_id and not is_assigned:
        return None
    db_task.status = new_status
    db_task.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_task)
    return task_to_dict(db_task)


def delete_task(db: Session, task_id: int) -> bool:
    """Удалить задачу"""
    db_task = get_task(db, task_id)
    if not db_task:
        return False
    db.query(TaskAssignmentDB).filter(TaskAssignmentDB.task_id == task_id).delete()
    db.query(TaskHierarchyDB).filter(
        or_(
            TaskHierarchyDB.parent_id == task_id,
            TaskHierarchyDB.child_id == task_id
        )
    ).delete()

    db.delete(db_task)
    db.commit()
    return True


def assign_users_to_task(db: Session, task_id: int, user_ids: List[int]) -> bool:
    """Назначить пользователей на задачу"""
    if not user_ids:
        return True
    db.query(TaskAssignmentDB).filter(TaskAssignmentDB.task_id == task_id).delete()
    for user_id in user_ids:
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if user:
            assignment = TaskAssignmentDB(task_id=task_id, user_id=user_id)
            db.add(assignment)

    db.commit()
    return True


def get_user_tasks(db: Session, user_id: int) -> List[TaskDB]:
    """Получить все задачи пользователя (созданные и назначенные)"""
    return get_tasks(db, user_id=user_id, limit=1000)


def get_task_stats(db: Session, user_id: Optional[int] = None) -> dict:
    """Получить статистику по задачам"""
    query = db.query(TaskDB.status, func.count(TaskDB.id))

    if user_id:
        query = query.join(TaskDB.assignments).filter(
            or_(
                TaskDB.creator_id == user_id,
                TaskAssignmentDB.user_id == user_id
            )
        )

    stats = query.group_by(TaskDB.status).all()

    result = {
        'total': 0,
        'open': 0,
        'in_progress': 0,
        'review': 0,
        'completed': 0
    }

    for status, count in stats:
        result[status.value] = count
        result['total'] += count

    return result


def create_task_hierarchy(db: Session, parent_id: int, child_id: int) -> Optional[dict]:
    """Создать связь родитель-потомок между задачами"""
    # Проверяем что задачи существуют
    parent = get_task(db, parent_id)
    child = get_task(db, child_id)

    if not parent or not child:
        return None
    existing_hierarchy = db.query(TaskHierarchyDB).filter(
        TaskHierarchyDB.parent_id == parent_id,
        TaskHierarchyDB.child_id == child_id
    ).first()

    if existing_hierarchy:
        return {
            "parent_id": existing_hierarchy.parent_id,
            "child_id": existing_hierarchy.child_id,
            "created_at": existing_hierarchy.created_at
        }

    hierarchy = TaskHierarchyDB(parent_id=parent_id, child_id=child_id)
    db.add(hierarchy)
    db.commit()
    db.refresh(hierarchy)

    return {
        "parent_id": hierarchy.parent_id,
        "child_id": hierarchy.child_id,
        "created_at": hierarchy.created_at
    }


def get_task_hierarchy(db: Session, task_id: int) -> dict:
    """Получить иерархию задачи"""
    task = get_task(db, task_id)
    if not task:
        return {}

    # Уникальные родители (используем set для удаления дубликатов)
    parent_relations = list(set(task.parent_relations))
    # Уникальные дети (используем set для удаления дубликатов)
    child_relations = list(set(task.child_relations))

    # Преобразуем задачи в словари для сериализации
    parents = [task_to_dict(rel.parent_task) for rel in parent_relations if rel.parent_task]
    children = [task_to_dict(rel.child_task) for rel in child_relations if rel.child_task]

    return {
        'task': task_to_dict(task),
        'parents': parents,
        'children': children
    }
