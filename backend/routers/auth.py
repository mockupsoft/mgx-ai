# -*- coding: utf-8 -*-
"""
Authentication Router

Handles user registration, login, logout, and token management.
Uses JWT tokens for authentication and bcrypt for password hashing.
"""

from datetime import datetime, timedelta
from typing import Optional
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_session
from backend.db.models.entities import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# HTTP Bearer token security
security = HTTPBearer()
optional_bearer = HTTPBearer(auto_error=False)

_ANON_EMAIL = "deepsite_anonymous@local"
_ANON_USERNAME = "deepsite_anonymous"


# Pydantic models
class UserRegister(BaseModel):
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class UserLogin(BaseModel):
    email_or_username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    email_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        # Try bcrypt directly first
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except Exception:
        # Fallback to passlib
        return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Bcrypt has a 72 byte limit, truncate if necessary
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    # Use bcrypt directly to avoid passlib's detection bug
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    return user


async def get_or_create_anonymous_deepsite_user(session: AsyncSession) -> User:
    """Single shared user for DeepSite when skip-auth is enabled."""
    result = await session.execute(select(User).where(User.email == _ANON_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        id=str(uuid4()),
        email=_ANON_EMAIL,
        username=_ANON_USERNAME,
        password_hash=get_password_hash(str(uuid4())),
        full_name="DeepSite (anonymous)",
        is_active=True,
        email_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_deepsite_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    """JWT user or anon user when settings.deepsite_skip_auth is true."""
    if settings.deepsite_skip_auth:
        return await get_or_create_anonymous_deepsite_user(session)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )
    return user


# Routes
@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    session: AsyncSession = Depends(get_session)
):
    """Register a new user."""
    # Check if email already exists
    result = await session.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists
    result = await session.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        email_verified=False
    )
    
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    
    logger.info(f"New user registered: {new_user.email} ({new_user.username})")
    
    # Create tokens
    access_token = create_access_token(data={"sub": new_user.id})
    refresh_token = create_refresh_token(data={"sub": new_user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    session: AsyncSession = Depends(get_session)
):
    """Login with email/username and password."""
    # Find user by email or username
    result = await session.execute(
        select(User).where(
            (User.email == login_data.email_or_username) |
            (User.username == login_data.email_or_username)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await session.commit()
    
    logger.info(f"User logged in: {user.email} ({user.username})")
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session)
):
    """Refresh access token using refresh token."""
    try:
        payload = jwt.decode(token_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token"
        )
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout():
    """Logout endpoint (client should discard tokens)."""
    # In a stateless JWT system, logout is handled client-side
    # For enhanced security, you could implement token blacklisting
    return {"message": "Logged out successfully"}


__all__ = ["router", "get_current_user", "get_deepsite_user"]
