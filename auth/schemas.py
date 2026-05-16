from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    username: str = Field(..., min_length=3, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Request model for token refresh."""

    token: str


class AuthResponse(BaseModel):
    """Response model for authentication success."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Response model for user information."""

    user_id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Response model for errors."""

    detail: str
    status_code: int


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
