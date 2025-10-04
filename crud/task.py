from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func
from typing import List, Optional
import datetime

from models.task import TaskDB, TaskHierarchyDB, TaskAssignmentDB, TaskStatus
from models.user import UserDB
from schemas.task import TaskCreate, TaskUpdate


def get_task(db: Session, task_id: int) -> Optional[TaskDB]:
    """Получить задачу по ID со всеми связями"""
    return db.query(TaskDB).options(
        joinedload(TaskDB.creator),
        joinedload(TaskDB.assignments).joinedload(TaskAssignmentDB.user),
        joinedload(TaskDB.parent_relations).joinedload(TaskHierarchyDB.parent_task),
        joinedload(TaskDB.child_relations).joinedload(TaskHierarchyDB.child_task)
    ).filter(TaskDB.id == task_id).first()


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
    query = db.query(TaskDB)

    # Добавляем joins для оптимизации
    if include_assignments:
        query = query.options(
            joinedload(TaskDB.creator),
            joinedload(TaskDB.assignments).joinedload(TaskAssignmentDB.user)
        )

    # Фильтр по пользователю (создатель или назначенный)
    if user_id:
        query = query.join(TaskDB.assignments).filter(
            or_(
                TaskDB.creator_id == user_id,
                TaskAssignmentDB.user_id == user_id
            )
        )

    # Фильтр по статусу
    if status:
        query = query.filter(TaskDB.status == TaskStatus(status))

    # Поиск по названию и описанию
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
    query = db.query(TaskDB)

    if user_id:
        query = query.join(TaskDB.assignments).filter(
            or_(
                TaskDB.creator_id == user_id,
                TaskAssignmentDB.user_id == user_id
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

    return query.count()


def create_task(db: Session, task: TaskCreate, creator_id: int) -> TaskDB:
    """Создать новую задачу"""
    db_task = TaskDB(
        title=task.title,
        description=task.description,
        due_date=task.due_date,
        creator_id=creator_id,
        status=TaskStatus.OPEN
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    # Добавляем назначенных пользователей
    if task.assigned_user_ids:
        assign_users_to_task(db, db_task.id, task.assigned_user_ids)

    return get_task(db, db_task.id)


def update_task(db: Session, task_id: int, task_update: TaskUpdate) -> Optional[TaskDB]:
    """Обновить задачу"""
    db_task = get_task(db, task_id)
    if not db_task:
        return None

    update_data = task_update.dict(exclude_unset=True)

    # Обновляем основные поля
    for field, value in update_data.items():
        if field != 'assigned_user_ids' and value is not None:
            setattr(db_task, field, value)

    # Обновляем статус если он передан
    if 'status' in update_data and update_data['status'] is not None:
        db_task.status = TaskStatus(update_data['status'])

    # Обновляем назначенных пользователей если переданы
    if 'assigned_user_ids' in update_data:
        assign_users_to_task(db, task_id, task_update.assigned_user_ids)

    db_task.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(db_task)

    return get_task(db, task_id)


def delete_task(db: Session, task_id: int) -> bool:
    """Удалить задачу"""
    db_task = get_task(db, task_id)
    if not db_task:
        return False

    # Удаляем связи с пользователями
    db.query(TaskAssignmentDB).filter(TaskAssignmentDB.task_id == task_id).delete()

    # Удаляем иерархические связи
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

    # Удаляем старые назначения
    db.query(TaskAssignmentDB).filter(TaskAssignmentDB.task_id == task_id).delete()

    # Добавляем новые назначения
    for user_id in user_ids:
        # Проверяем существование пользователя
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


def create_task_hierarchy(db: Session, parent_id: int, child_id: int) -> Optional[TaskHierarchyDB]:
    """Создать связь родитель-потомок между задачами"""
    # Проверяем что задачи существуют
    parent = get_task(db, parent_id)
    child = get_task(db, child_id)

    if not parent or not child:
        return None

    # Проверяем что связь не создает цикл
    if _would_create_cycle(db, parent_id, child_id):
        return None

    hierarchy = TaskHierarchyDB(parent_id=parent_id, child_id=child_id)
    db.add(hierarchy)
    db.commit()
    db.refresh(hierarchy)
    return hierarchy


def get_task_hierarchy(db: Session, task_id: int) -> dict:
    """Получить иерархию задачи (родителей и потомков)"""
    task = get_task(db, task_id)
    if not task:
        return {}

    return {
        'task': task,
        'parents': [rel.parent_task for rel in task.parent_relations],
        'children': [rel.child_task for rel in task.child_relations]
    }


def _would_create_cycle(db: Session, parent_id: int, child_id: int) -> bool:
    """Проверить создаст ли связь цикл в иерархии"""
    # Простая проверка - если child уже является родителем parent
    existing_relation = db.query(TaskHierarchyDB).filter(
        and_(
            TaskHierarchyDB.parent_id == child_id,
            TaskHierarchyDB.child_id == parent_id
        )
    ).first()

    return existing_relation is not None