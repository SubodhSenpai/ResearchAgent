import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.exc import IntegrityError
from .models import User, APIToken
from .password_manager import PasswordManager
from .jwt_handler import JWTHandler
from datetime import datetime, timedelta
from config.settings import settings
import uuid

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages user authentication, registration, and token operations."""

    def __init__(self, db: DBSession):
        self.db = db
        self.password_mgr = PasswordManager()
        self.jwt_handler = JWTHandler()

    def register(self, username: str, email: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """Register a new user.

        Args:
            username: Desired username
            email: User email
            password: Plain text password

        Returns:
            Tuple of (User object, error message or None)
        """
        try:
            # Validate inputs
            if not username or len(username) < 3:
                return None, "Username must be at least 3 characters"

            if not email or "@" not in email:
                return None, "Invalid email address"

            if not password or len(password) < 8:
                return None, "Password must be at least 8 characters"

            # Hash password
            password_hash = self.password_mgr.hash_password(password)

            # Create user
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                is_active=True,
            )

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            logger.info(f"User registered: {username} ({user.user_id})")
            return user, None

        except IntegrityError as e:
            self.db.rollback()
            if "username" in str(e):
                return None, "Username already exists"
            elif "email" in str(e):
                return None, "Email already registered"
            else:
                return None, "Registration failed"
        except Exception as e:
            self.db.rollback()
            logger.error(f"Registration error: {e}")
            return None, "Registration failed"

    def login(self, username: str, password: str) -> Tuple[Optional[str], Optional[str]]:
        """Authenticate user and return JWT token.

        Args:
            username: Username
            password: Plain text password

        Returns:
            Tuple of (JWT token, error message or None)
        """
        try:
            # Find user
            user = self.db.query(User).filter_by(username=username).first()
            if not user:
                return None, "Invalid username or password"

            # Verify password
            if not self.password_mgr.verify_password(password, user.password_hash):
                return None, "Invalid username or password"

            if not user.is_active:
                return None, "User account is inactive"

            # Update last login
            user.last_login = datetime.utcnow()
            self.db.commit()

            # Generate JWT
            token = self.jwt_handler.generate_jwt(user.user_id)

            logger.info(f"User logged in: {username}")
            return token, None

        except Exception as e:
            logger.error(f"Login error: {e}")
            return None, "Login failed"

    def refresh(self, token: str) -> Tuple[Optional[str], Optional[str]]:
        """Refresh an expired JWT token.

        Args:
            token: Existing JWT token

        Returns:
            Tuple of (new JWT token, error message or None)
        """
        try:
            # Try to refresh
            new_token = self.jwt_handler.refresh_token(token)
            if not new_token:
                return None, "Invalid token"

            logger.info("JWT token refreshed")
            return new_token, None

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None, "Token refresh failed"

    def get_user(self, user_id: str) -> Optional[User]:
        """Fetch user by ID.

        Args:
            user_id: User ID

        Returns:
            User object or None
        """
        try:
            return self.db.query(User).filter_by(user_id=user_id).first()
        except Exception as e:
            logger.error(f"Get user error: {e}")
            return None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetch user by username.

        Args:
            username: Username

        Returns:
            User object or None
        """
        try:
            return self.db.query(User).filter_by(username=username).first()
        except Exception as e:
            logger.error(f"Get user by username error: {e}")
            return None

    def revoke_token(self, user_id: str) -> bool:
        """Revoke all API tokens for a user (logout).

        Args:
            user_id: User ID

        Returns:
            True if successful, False otherwise
        """
        try:
            tokens = self.db.query(APIToken).filter_by(user_id=user_id, is_revoked=False).all()
            for token in tokens:
                token.is_revoked = True
            self.db.commit()

            logger.info(f"Tokens revoked for user {user_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Token revocation error: {e}")
            return False

    def create_api_token(self, user_id: str, expires_in_days: int = 30) -> Tuple[Optional[str], Optional[str]]:
        """Create an API token for a user.

        Args:
            user_id: User ID
            expires_in_days: Days until token expires

        Returns:
            Tuple of (token_hash, error message or None)
        """
        try:
            token = str(uuid.uuid4())
            token_hash = self.password_mgr.hash_password(token)

            api_token = APIToken(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            )

            self.db.add(api_token)
            self.db.commit()

            logger.info(f"API token created for user {user_id}")
            return token, None

        except Exception as e:
            self.db.rollback()
            logger.error(f"API token creation error: {e}")
            return None, "Token creation failed"

    def verify_api_token(self, token: str) -> Optional[str]:
        """Verify an API token and return user_id if valid.

        Args:
            token: API token

        Returns:
            User ID if valid, None otherwise
        """
        try:
            # This would need to hash the token and compare
            # For now, simplified - in production use more secure comparison
            logger.warning("API token verification not yet implemented")
            return None
        except Exception as e:
            logger.error(f"API token verification error: {e}")
            return None
