import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages research sessions and chat history in PostgreSQL."""

    def __init__(self, db: DBSession):
        self.db = db

    def create_session(self, user_id: str, query: str) -> Optional[str]:
        """Create a new research session.

        Args:
            user_id: User ID
            query: Research query

        Returns:
            Session ID or None if failed
        """
        try:
            # Import here to avoid circular imports
            from auth.models import Session

            session = Session(
                user_id=user_id,
                query=query,
                status="running",
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            logger.info(f"Session created: {session.session_id} for user {user_id}")
            return str(session.session_id)

        except Exception as e:
            self.db.rollback()
            logger.error(f"Create session error: {e}")
            return None

    def get_session(self, session_id: str):
        """Fetch a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session object or None
        """
        try:
            from auth.models import Session

            return self.db.query(Session).filter_by(session_id=session_id).first()

        except Exception as e:
            logger.error(f"Get session error: {e}")
            return None

    def get_user_sessions(self, user_id: str, limit: int = 50, offset: int = 0) -> List:
        """Get all sessions for a user (paginated).

        Args:
            user_id: User ID
            limit: Number of sessions to return
            offset: Pagination offset

        Returns:
            List of Session objects
        """
        try:
            from auth.models import Session

            return (
                self.db.query(Session)
                .filter_by(user_id=user_id)
                .order_by(desc(Session.created_at))
                .offset(offset)
                .limit(limit)
                .all()
            )

        except Exception as e:
            logger.error(f"Get user sessions error: {e}")
            return []

    def get_user_sessions_count(self, user_id: str) -> int:
        """Get total count of sessions for a user.

        Args:
            user_id: User ID

        Returns:
            Total session count
        """
        try:
            from auth.models import Session

            return self.db.query(Session).filter_by(user_id=user_id).count()

        except Exception as e:
            logger.error(f"Get sessions count error: {e}")
            return 0

    def update_session_result(
        self,
        session_id: str,
        final_answer: str,
        quality_score: float,
        tokens_used: int = 0,
        cost_estimate: float = 0.0,
    ) -> bool:
        """Update session with research results.

        Args:
            session_id: Session ID
            final_answer: Final research answer
            quality_score: Quality score (0-1)
            tokens_used: Number of tokens used
            cost_estimate: Estimated cost

        Returns:
            True if successful, False otherwise
        """
        try:
            from auth.models import Session

            session = self.db.query(Session).filter_by(session_id=session_id).first()
            if not session:
                return False

            session.final_answer = final_answer
            session.quality_score = quality_score
            session.tokens_used = tokens_used
            session.cost_estimate = cost_estimate
            session.status = "completed"
            session.updated_at = datetime.utcnow()

            self.db.commit()

            logger.info(
                f"Session {session_id} updated. Quality: {quality_score:.2f}, Tokens: {tokens_used}"
            )
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Update session error: {e}")
            return False

    def mark_session_interrupted(self, session_id: str) -> bool:
        """Mark a session as interrupted.

        Args:
            session_id: Session ID

        Returns:
            True if successful, False otherwise
        """
        try:
            from auth.models import Session

            session = self.db.query(Session).filter_by(session_id=session_id).first()
            if not session:
                return False

            session.status = "interrupted"
            session.updated_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Session {session_id} marked as interrupted")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Mark interrupted error: {e}")
            return False

    def delete_session(self, session_id: str, soft_delete: bool = True) -> bool:
        """Delete or archive a session.

        Args:
            session_id: Session ID
            soft_delete: If True, mark as deleted. If False, hard delete.

        Returns:
            True if successful, False otherwise
        """
        try:
            from auth.models import Session

            session = self.db.query(Session).filter_by(session_id=session_id).first()
            if not session:
                return False

            if soft_delete:
                session.status = "archived"
                session.updated_at = datetime.utcnow()
                self.db.commit()
            else:
                self.db.delete(session)
                self.db.commit()

            logger.info(f"Session {session_id} deleted")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Delete session error: {e}")
            return False

    def get_session_history(self, session_id: str) -> List:
        """Get chat history for a session.

        Args:
            session_id: Session ID

        Returns:
            List of ChatHistory objects
        """
        try:
            from auth.models import ChatHistory

            return (
                self.db.query(ChatHistory)
                .filter_by(session_id=session_id)
                .order_by(ChatHistory.created_at)
                .all()
            )

        except Exception as e:
            logger.error(f"Get session history error: {e}")
            return []

    def save_to_history(
        self,
        session_id: str,
        user_id: str,
        message_type: str,
        content: str,
        embedding_vector: Optional[List] = None,
        relevance_score: float = 0.0,
    ) -> bool:
        """Save a message to chat history.

        Args:
            session_id: Session ID
            user_id: User ID
            message_type: "user" or "assistant"
            content: Message content
            embedding_vector: Optional embedding vector
            relevance_score: Optional relevance score

        Returns:
            True if successful, False otherwise
        """
        try:
            from auth.models import ChatHistory

            history = ChatHistory(
                session_id=session_id,
                user_id=user_id,
                message_type=message_type,
                content=content,
                embedding_vector=embedding_vector,
                relevance_score=relevance_score,
            )

            self.db.add(history)
            self.db.commit()

            logger.info(f"Message saved to history for session {session_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Save to history error: {e}")
            return False
