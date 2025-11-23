from pydantic import BaseModel, validator, Field
from datetime import datetime
from typing import Optional

from models.user import UserRole


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    role: UserRole
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class User(UserResponse):
    pass