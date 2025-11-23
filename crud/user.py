from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from models.user import UserDB, UserRole
from schemas.user import UserCreate, UserUpdate


def get_user(db: Session, user_id: int) -> Optional[UserDB]:
    return db.query(UserDB).filter(UserDB.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[UserDB]:
    return db.query(UserDB).filter(UserDB.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100, role: Optional[UserRole] = None,
              search: Optional[str] = None) -> List[UserDB]:
    query = db.query(UserDB)

    if role:
        query = query.filter(UserDB.role == role)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(or_(UserDB.username.ilike(search_filter), UserDB.full_name.ilike(search_filter)))

    return query.order_by(UserDB.username).offset(skip).limit(limit).all()


def get_users_count(db: Session, role: Optional[UserRole] = None, search: Optional[str] = None) -> int:
    query = db.query(UserDB)

    if role:
        query = query.filter(UserDB.role == role)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(or_(UserDB.username.ilike(search_filter), UserDB.full_name.ilike(search_filter)))

    return query.count()


def create_user(db: Session, user: UserCreate) -> Optional[UserDB]:
    if get_user_by_username(db, user.username):
        return None

    db_user = UserDB(username=user.username, full_name=user.full_name, role=user.role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[UserDB]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    update_data = user_update.model_dump(exclude_unset=True)

    if 'username' in update_data and update_data['username'] != db_user.username:
        if get_user_by_username(db, update_data['username']):
            return None

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


def get_users_by_role(db: Session, role: UserRole) -> List[UserDB]:
    return db.query(UserDB).filter(UserDB.role == role).order_by(UserDB.username).all()


def change_user_role(db: Session, user_id: int, new_role: UserRole) -> Optional[UserDB]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None

    db_user.role = new_role
    db.commit()
    db.refresh(db_user)
    return db_user

def search_users(db: Session, search_term: str, limit: int = 50) -> List[UserDB]:
    search_filter = f"%{search_term}%"
    return db.query(UserDB).filter(
        or_(UserDB.username.ilike(search_filter), UserDB.full_name.ilike(search_filter))
    ).limit(limit).all()