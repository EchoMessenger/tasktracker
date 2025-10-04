from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
import datetime
from database import Base


class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Связи
    created_tasks = relationship("TaskDB", back_populates="creator", foreign_keys="TaskDB.creator_id")
    assigned_tasks = relationship("TaskAssignmentDB", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
