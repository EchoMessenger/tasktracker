from sqlalchemy.orm import Session
from models.user import UserDB
from schemas.user import UserCreate

def create_user(db: Session, user: UserCreate):
    db_user = UserDB(username=user.username, full_name=user.full_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(UserDB).offset(skip).limit(limit).all()

def get_user(db: Session, user_id: int):
    return db.query(UserDB).filter(UserDB.id == user_id).first()

def delete_user(db: Session, user_id: int):
    db_user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user