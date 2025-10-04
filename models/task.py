from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
import datetime
import enum
from database import Base


class TaskStatus(enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"


class TaskDB(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.OPEN)

    # Создатель задачи
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Связи
    creator = relationship("UserDB", back_populates="created_tasks")

    # Иерархия задач (родительские связи)
    parent_relations = relationship(
        "TaskHierarchyDB",
        foreign_keys="TaskHierarchyDB.child_id",
        back_populates="child_task"
    )
    child_relations = relationship(
        "TaskHierarchyDB",
        foreign_keys="TaskHierarchyDB.parent_id",
        back_populates="parent_task"
    )

    # Назначения на пользователей
    assignments = relationship("TaskAssignmentDB", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status='{self.status}')>"


class TaskHierarchyDB(Base):
    __tablename__ = "task_hierarchy"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Связи
    parent_task = relationship("TaskDB", foreign_keys=[parent_id], back_populates="child_relations")
    child_task = relationship("TaskDB", foreign_keys=[child_id], back_populates="parent_relations")

    def __repr__(self):
        return f"<TaskHierarchy(parent_id={self.parent_id}, child_id={self.child_id})>"


class TaskAssignmentDB(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Связи
    task = relationship("TaskDB", back_populates="assignments")
    user = relationship("UserDB", back_populates="assigned_tasks")

    def __repr__(self):
        return f"<TaskAssignment(task_id={self.task_id}, user_id={self.user_id})>"