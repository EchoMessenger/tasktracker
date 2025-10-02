from pydantic import BaseModel
from datetime import datetime


class UserBase(BaseModel):
    username: str
    full_name: str = None


class UserCreate(UserBase):
    pass


class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True