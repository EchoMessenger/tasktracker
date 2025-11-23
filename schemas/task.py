from pydantic import BaseModel, validator, Field
from datetime import datetime
from typing import List, Optional
from models.task import TaskStatus
from schemas.user import UserResponse

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_user_ids: List[int] = Field(default_factory=list)

    @validator('title')
    def title_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()

class TaskCreate(TaskBase):
    creator_id: int = Field(..., description="ID пользователя-создателя задачи")

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[TaskStatus] = None
    assigned_user_ids: Optional[List[int]] = None

class TaskStatusUpdate(BaseModel):
    status: TaskStatus

class TaskResponse(TaskBase):
    id: int
    status: TaskStatus
    creator_id: int
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    assigned_users: List[UserResponse] = []

    class Config:
        from_attributes = True

class Task(TaskResponse):
    pass