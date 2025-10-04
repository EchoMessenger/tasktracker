from pydantic import BaseModel, validator
from datetime import datetime
from typing import List, Optional
from .user import User


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None

    @validator('title')
    def title_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()


class TaskCreate(TaskBase):
    assigned_user_ids: Optional[List[int]] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    assigned_user_ids: Optional[List[int]] = None

    @validator('status')
    def status_validator(cls, v):
        if v is not None:
            valid_statuses = ['open', 'in_progress', 'review', 'completed']
            if v not in valid_statuses:
                raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v


class TaskStatusUpdate(BaseModel):
    status: str

    @validator('status')
    def valid_status(cls, v):
        valid_statuses = ['open', 'in_progress', 'review', 'completed']
        if v not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v


class Task(TaskBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    creator_id: int
    creator: Optional[User] = None
    assigned_users: List[User] = []

    class Config:
        from_attributes = True
