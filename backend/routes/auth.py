"""
Authentication routes.
Login, register, get current user, update profile.
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.services.auth_service import (
    create_access_token,
    verify_access_token,
    authenticate_user,
    create_user,
    get_user_by_id,
)

router = APIRouter(tags=["auth"])

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


class UserRegister(BaseModel):
    """User registration request."""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6, max_length=200)


class UserLogin(BaseModel):
    """User login request (username or email)."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class UserResponse(BaseModel):
    """User response (password never returned)."""
    id: int
    username: str
    email: Optional[str]
    is_active: bool
    created_at: Optional[str] = None


class UserUpdate(BaseModel):
    """User profile update request."""
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6, max_length=200)


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> Optional[int]:
    """
    Dependency to get current user ID from JWT token.
    """
    if token:
        payload = verify_access_token(token)
        if payload:
            sub = payload.get("sub")
            try:
                return int(sub) if sub is not None else None
            except (TypeError, ValueError):
                return None
    return None


def get_current_user(
    current_user_id: Optional[int] = Depends(get_current_user_id),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to get current user object from JWT token.
    """
    if not current_user_id:
        return None

    return get_user_by_id(db, current_user_id)


def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    """
    Dependency that requires authentication.
    Raises 401 if not authenticated.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    return user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user.

    - Username must be unique and 3-50 chars
    - Email is optional but must be unique if provided
    - Password must be 6+ chars
    """
    from backend.services.auth_service import get_user_by_username, get_user_by_email

    existing_user = get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    if user_data.email:
        existing_email = get_user_by_email(db, user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    user = create_user(
        db=db,
        username=user_data.username.strip(),
        email=user_data.email.strip() if user_data.email else None,
        password=user_data.password,
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.post("/login", response_model=Token)
def login(form_data: UserLogin, db: Session = Depends(get_db)):
    """
    Login user.

    Accepts either username or email.
    Returns JWT access token.
    """
    username = form_data.username.strip()
    password = form_data.password

    # Временный debug. Потом можешь удалить.
    print("LOGIN username:", repr(username))
    print("LOGIN password length:", len(password))

    user = authenticate_user(db, username, password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    access_token_expires = timedelta(minutes=60)
    token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(require_auth)):
    """
    Get current authenticated user.
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.put("/me", response_model=UserResponse)
def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Update current user profile.
    """
    from backend.services.auth_service import get_user_by_email, get_password_hash

    if user_update.email and user_update.email != current_user.email:
        existing = get_user_by_email(db, user_update.email)
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        current_user.email = user_update.email.strip()

    if user_update.password:
        current_user.password_hash = get_password_hash(user_update.password)

    db.commit()
    db.refresh(current_user)

    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.post("/logout")
def logout(current_user: User = Depends(require_auth)):
    """
    Logout user.
    Client-side operation: token should be removed from storage.
    """
    return {"message": "Logged out successfully"}