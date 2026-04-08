# -*- coding: utf-8 -*-
"""
Authentication Middleware

JWT token validation middleware for protecting routes.
"""

from typing import Optional
import logging

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_session_manager
from backend.db.models.entities import User

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# JWT settings
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"


async def get_current_user_from_token(token: str, session: AsyncSession) -> Optional[User]:
    """Get user from JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to add current_user to request state for authenticated requests."""
    
    def __init__(self, app: ASGIApp, optional: bool = False):
        """
        Initialize auth middleware.
        
        Args:
            app: ASGI application
            optional: If True, missing/invalid tokens don't cause errors (user will be None)
        """
        super().__init__(app)
        self.optional = optional
    
    async def dispatch(self, request: Request, call_next):
        """Process request and add user to state if authenticated."""
        # Skip auth for certain paths
        skip_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/auth/register",
            "/api/auth/login",
        ]
        
        if any(request.url.path.startswith(path) for path in skip_paths):
            request.state.current_user = None
            return await call_next(request)
        
        # Try to get token from Authorization header
        authorization = request.headers.get("Authorization")
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
        
        if token:
            try:
                session_manager = get_session_manager()
                async with session_manager.session() as session:
                    user = await get_current_user_from_token(token, session)
                    request.state.current_user = user
                    request.state.user_id = user.id if user else None
            except Exception as e:
                logger.warning(f"Error validating token: {e}")
                if not self.optional:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Could not validate credentials"
                    )
                request.state.current_user = None
                request.state.user_id = None
        else:
            request.state.current_user = None
            request.state.user_id = None
            if not self.optional and request.url.path.startswith("/api/"):
                # Only require auth for API endpoints (not auth endpoints themselves)
                if not any(request.url.path.startswith(path) for path in ["/api/auth", "/api/health"]):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Not authenticated"
                    )
        
        return await call_next(request)


__all__ = ["AuthMiddleware", "get_current_user_from_token"]
