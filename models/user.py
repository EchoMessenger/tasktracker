import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.orm import relationship
import datetime
from database import Base


class UserRole(enum.Enum):
    USER = "user"
    MANAGER = "manager"
    ADMIN = "admin"


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False, index=True)  # Используем Enum(UserRole)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_tasks = relationship("TaskDB", back_populates="creator", foreign_keys="TaskDB.creator_id", cascade="all, delete-orphan")
    assigned_tasks = relationship("TaskAssignmentDB", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserDB(id={self.id}, username='{self.username}', role='{self.role.value}')>"

    def can_manage_tasks(self):
        """Может ли пользователь управлять задачами других"""
        return self.role in [UserRole.MANAGER, UserRole.ADMIN]

    def can_delete_tasks(self):
        """Может ли пользователь удалять любые задачи"""
        return self.role == UserRole.ADMIN

    def can_create_task(self) -> bool:
        """Может ли пользователь создавать задачи"""
        return self.role in [UserRole.MANAGER, UserRole.ADMIN]