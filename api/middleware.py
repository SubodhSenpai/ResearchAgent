import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from auth.jwt_handler import JWTHandler
from auth.database import get_db
from auth.models import User
from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)

security = HTTPBearer()
jwt_handler = JWTHandler()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DBSession = Depends(get_db),
) -> User:
    """Extract and validate JWT token, return current user.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        # Verify JWT
        payload = jwt_handler.verify_jwt(token)
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")

        # Fetch user from database
        user = db.query(User).filter_by(user_id=user_id).first()

        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is inactive")

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"JWT validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user_optional(request: Request, db: DBSession = Depends(get_db)) -> Optional[User]:
    """Extract JWT token if present, return user if valid (optional auth).

    Args:
        request: HTTP request
        db: Database session

    Returns:
        User object if authenticated, None otherwise
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]

    try:
        payload = jwt_handler.verify_jwt(token)
        user_id = payload.get("user_id")

        if not user_id:
            return None

        user = db.query(User).filter_by(user_id=user_id).first()

        if user and user.is_active:
            return user

        return None

    except Exception as e:
        logger.debug(f"Optional JWT validation failed: {e}")
        return None


def verify_ownership(user_id: str, resource_user_id: str) -> bool:
    """Verify that a user owns a resource.

    Args:
        user_id: Authenticated user ID
        resource_user_id: Owner of the resource

    Returns:
        True if user owns resource, False otherwise
    """
    return str(user_id) == str(resource_user_id)


class NormalizePathMiddleware(BaseHTTPMiddleware):
    """Collapse duplicate slashes so //auth/login matches /auth/login."""

    async def dispatch(self, request: Request, call_next):
        path = request.scope.get("path", "")
        if "//" in path:
            normalized = path
            while "//" in normalized:
                normalized = normalized.replace("//", "/")
            request.scope["path"] = normalized
        return await call_next(request)
