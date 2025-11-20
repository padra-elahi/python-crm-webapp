from fastapi import Request, Depends
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from database import get_db
from models import User

def login_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if user and bcrypt.verify(password, user.password):
        return user
    return None

def register_user(db: Session, username: str, password: str, role: str, section: str):
    if db.query(User).filter(User.username == username).first():
        return None
    user = User(
        username=username, 
        password=bcrypt.hash(password), 
        role=role, 
        section=section # Save the user's section
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == int(user_id)).first()
    return user