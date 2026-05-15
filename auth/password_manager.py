import bcrypt
import logging

logger = logging.getLogger(__name__)


class PasswordManager:
    """Handles password hashing and verification using bcrypt."""

    SALT_ROUNDS = 12

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt with salt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        salt = bcrypt.gensalt(rounds=PasswordManager.SALT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain text password to verify
            password_hash: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
