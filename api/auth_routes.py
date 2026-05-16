import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
from uuid import uuid4

from auth.auth_manager import AuthManager
from auth.database import get_db
from auth.models import User
from auth.schemas import RegisterRequest, LoginRequest, AuthResponse, UserResponse, MessageResponse
from config.settings import settings
from api.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest, db: DBSession = Depends(get_db)):
    """Register a new user account.

    Args:
        request: Registration request with username, email, password
        db: Database session

    Returns:
        User object with ID and metadata
    """
    auth_manager = AuthManager(db)

    user, error = auth_manager.register(request.username, request.email, request.password)

    if error:
        logger.warning(f"Registration failed: {error}")
        raise HTTPException(status_code=400, detail=error)

    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: DBSession = Depends(get_db)):
    """Authenticate user and return JWT token.

    Args:
        request: Login request with username and password
        db: Database session

    Returns:
        JWT access token and metadata
    """
    auth_manager = AuthManager(db)

    token, error = auth_manager.login(request.username, request.password)

    if error:
        logger.warning(f"Login failed for user {request.username}: {error}")
        raise HTTPException(status_code=401, detail=error)

    return AuthResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=settings.jwt_expiry,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(request: dict, db: DBSession = Depends(get_db)):
    """Refresh an expired JWT token.

    Args:
        request: Request with 'token' field
        db: Database session

    Returns:
        New JWT access token
    """
    if "token" not in request:
        raise HTTPException(status_code=400, detail="Token is required")

    auth_manager = AuthManager(db)

    token, error = auth_manager.refresh(request["token"])

    if error:
        logger.warning(f"Token refresh failed: {error}")
        raise HTTPException(status_code=401, detail=error)

    return AuthResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=settings.jwt_expiry,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information.

    Args:
        current_user: Current user from JWT

    Returns:
        User object with ID and metadata
    """
    return UserResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login=current_user.last_login,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user), db: DBSession = Depends(get_db)):
    """Logout user and revoke tokens.

    Args:
        current_user: Current user from JWT
        db: Database session

    Returns:
        Success message
    """
    auth_manager = AuthManager(db)

    success = auth_manager.revoke_token(current_user.user_id)

    if not success:
        logger.warning(f"Logout failed for user {current_user.user_id}")
        raise HTTPException(status_code=500, detail="Logout failed")

    logger.info(f"User logged out: {current_user.username}")
    return MessageResponse(message="Logged out successfully")
