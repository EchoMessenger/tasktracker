from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.user import User, UserCreate, UserUpdate
from schemas.response import StandardResponse, PaginatedResponse
import crud.user as crud

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Создать нового пользователя"""
    # Проверяем уникальность username (email больше не проверяем)
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    user_created = crud.create_user(db=db, user=user)
    return StandardResponse(
        message="User created successfully",
        data=user_created
    )


@router.get("/", response_model=PaginatedResponse[User])
def read_users(
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
        db: Session = Depends(get_db)
):
    """Получить список пользователей"""
    users = crud.get_users(db, skip=skip, limit=limit)
    return PaginatedResponse(
        message="Users retrieved successfully",
        data=users,
        pagination={
            "total": len(users),
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "pages": (len(users) + limit - 1) // limit if limit > 0 else 1
        }
    )


@router.get("/{user_id}", response_model=StandardResponse)
def read_user(user_id: int, db: Session = Depends(get_db)):
    """Получить пользователя по ID"""
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return StandardResponse(
        message="User retrieved successfully",
        data=db_user
    )


@router.put("/{user_id}", response_model=StandardResponse)
def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """Обновить данные пользователя"""
    db_user = crud.update_user(db, user_id=user_id, user_update=user)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return StandardResponse(
        message="User updated successfully",
        data=db_user
    )


@router.delete("/{user_id}", response_model=StandardResponse)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Удалить пользователя"""
    success = crud.delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return StandardResponse(
        message="User deleted successfully",
        data=None
    )


@router.post("/authenticate", response_model=StandardResponse)
def authenticate_user(
        username: str = Query(..., description="Username"),
        password: str = Query(..., description="Password"),
        db: Session = Depends(get_db)
):
    """Аутентификация пользователя по username"""
    user = crud.authenticate_user(db, username=username, password=password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    return StandardResponse(
        message="Authentication successful",
        data=user
    )
