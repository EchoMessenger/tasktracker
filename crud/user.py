import bcrypt
from sqlalchemy.orm import Session
from typing import List, Optional

from models.user import UserDB
from schemas.user import UserCreate, UserUpdate


def get_user(db: Session, user_id: int) -> Optional[UserDB]:
    return db.query(UserDB).filter(UserDB.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[UserDB]:
    return db.query(UserDB).filter(UserDB.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[UserDB]:
    return db.query(UserDB).offset(skip).limit(limit).all()


def create_user(db: Session, user: UserCreate) -> UserDB:
    # Хешируем пароль
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    db_user = UserDB(
        username=user.username,
        full_name=user.full_name,
        password_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[UserDB]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user_update.dict(exclude_unset=True)

    # Если обновляется пароль - хешируем его
    if 'password' in update_data:
        update_data['password_hash'] = bcrypt.hashpw(
            update_data.pop('password').encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    for field, value in update_data.items():
        if value is not None:
            setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    db_user = get_user(db, user_id)
    if not db_user:
        return False

    db.delete(db_user)
    db.commit()
    return True


def authenticate_user(db: Session, username: str, password: str) -> Optional[UserDB]:
    user = get_user_by_username(db, username)

    if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return user
    return None
