from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import Settings
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, User as UserSchema

settings = Settings()
router = APIRouter()

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(deps.get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.email, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/register", response_model=UserSchema)
def register_user(
    *,
    db: Session = Depends(deps.get_db),
    user_in: UserCreate,
) -> Any:
    """
    Create new user.
    """
    print(f"[Register] Attempting to register user: {user_in.email}")
    try:
        user = db.query(User).filter(User.email == user_in.email).first()
        if user:
            print(f"[Register] User already exists: {user.email}")
            raise HTTPException(
                status_code=400,
                detail="The user with this username already exists in the system.",
            )
        
        user = User(
            email=user_in.email,
            hashed_password=security.get_password_hash(user_in.password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[Register] User created successfully: {user.id}")
        return user
    except Exception as e:
        print(f"[Register] Error: {str(e)}")
        # 如果是 HTTPException 直接抛出
        if isinstance(e, HTTPException):
            raise e
        # 其他数据库错误等
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/me", response_model=UserSchema)
def read_users_me(
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get current user.
    """
    return current_user
