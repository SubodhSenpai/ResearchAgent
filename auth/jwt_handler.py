import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config.settings import settings

logger = logging.getLogger(__name__)


class JWTHandler:
    """Handles JWT token generation, validation, and decoding."""

    @staticmethod
    def generate_jwt(user_id: str) -> str:
        """Generate a JWT token for a user.

        Args:
            user_id: User ID to encode in token

        Returns:
            JWT token string
        """
        payload = {
            "user_id": str(user_id),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(seconds=settings.jwt_expiry),
        }

        token = jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

        logger.info(f"JWT generated for user {user_id}")
        return token

    @staticmethod
    def verify_jwt(token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload dictionary

        Raises:
            jwt.InvalidTokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            raise

    @staticmethod
    def decode_jwt(token: str) -> Optional[Dict[str, Any]]:
        """Decode JWT without verification (for refresh token flow).

        Args:
            token: JWT token string

        Returns:
            Decoded payload dictionary or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
            )
            return payload
        except Exception as e:
            logger.error(f"JWT decode error: {e}")
            return None

    @staticmethod
    def refresh_token(token: str) -> Optional[str]:
        """Refresh an existing JWT token.

        Args:
            token: Existing JWT token

        Returns:
            New JWT token or None if refresh fails
        """
        try:
            # Decode without verification
            payload = JWTHandler.decode_jwt(token)
            if not payload or "user_id" not in payload:
                return None

            # Generate new token
            new_token = JWTHandler.generate_jwt(payload["user_id"])
            logger.info(f"JWT refreshed for user {payload['user_id']}")
            return new_token
        except Exception as e:
            logger.error(f"JWT refresh error: {e}")
            return None
