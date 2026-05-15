import logging
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages long-term memory and chat history for users."""

    def __init__(self, db: DBSession, session_memory=None):
        self.db = db
        self.chroma = session_memory  # ChromaDB instance for semantic search

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

    def get_history(self, session_id: str) -> List:
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
            logger.error(f"Get history error: {e}")
            return []

    def get_user_memory(self, user_id: str, limit: int = 10) -> List:
        """Get user's past research sessions for context.

        Args:
            user_id: User ID
            limit: Maximum sessions to return

        Returns:
            List of Session objects with final answers
        """
        try:
            from auth.models import Session
            from sqlalchemy import desc

            return (
                self.db.query(Session)
                .filter_by(user_id=user_id, status="completed")
                .order_by(desc(Session.created_at))
                .limit(limit)
                .all()
            )

        except Exception as e:
            logger.error(f"Get user memory error: {e}")
            return []

    def search_memory(self, query: str, user_id: str, k: int = 5) -> List[dict]:
        """Search user's past research using semantic similarity.

        Args:
            query: Search query
            user_id: User ID
            k: Number of results to return

        Returns:
            List of similar past sessions
        """
        try:
            if not self.chroma:
                logger.warning("ChromaDB not initialized")
                return []

            # Use ChromaDB for semantic search with user filter
            return self.chroma.retrieve_similar(query, user_id=user_id, k=k)

        except Exception as e:
            logger.error(f"Search memory error: {e}")
            return []

    def get_relevant_history(self, query: str, user_id: str, k: int = 5) -> str:
        """Get relevant past conversations formatted for agent context.

        Args:
            query: Current query
            user_id: User ID
            k: Number of results

        Returns:
            Formatted string of relevant past conversations
        """
        try:
            # Search for similar past queries
            similar_sessions = self.search_memory(query, user_id, k)

            if not similar_sessions:
                return "No relevant past research found."

            # Format for agent context
            context = "## Relevant Past Research:\n\n"
            for i, session in enumerate(similar_sessions, 1):
                context += f"**{i}. Query:** {session.get('query', 'N/A')}\n"
                context += f"   **Answer:** {session.get('answer', 'N/A')[:200]}...\n"
                context += (
                    f"   **Quality:** {session.get('quality_score', 0):.2f}/1.0\n"
                )
                context += f"   **Similarity:** {session.get('similarity', 0):.2%}\n\n"

            return context

        except Exception as e:
            logger.error(f"Get relevant history error: {e}")
            return "Error retrieving past research."

    def format_user_memory(self, sessions: List, limit: int = 3) -> str:
        """Format user's recent successful research for context injection.

        Args:
            sessions: List of Session objects
            limit: Maximum sessions to include

        Returns:
            Formatted string of user's recent research
        """
        if not sessions or len(sessions) == 0:
            return "User has no previous research history."

        context = "## Your Recent Research:\n\n"
        for i, session in enumerate(sessions[:limit], 1):
            context += f"**{i}. {session.query[:60]}...**\n"
            context += f"   Answer: {(session.final_answer or 'N/A')[:150]}...\n"
            context += f"   Quality: {session.quality_score:.2f}/1.0\n"
            context += f"   Date: {session.created_at.strftime('%Y-%m-%d')}\n\n"

        return context

    def get_similar_questions(self, query: str, user_id: str, k: int = 3) -> List[str]:
        """Find similar questions the user has asked before.

        Args:
            query: Current query
            user_id: User ID
            k: Number of similar questions to return

        Returns:
            List of similar question strings
        """
        try:
            similar = self.search_memory(query, user_id, k)
            return [s.get("query", "") for s in similar if s.get("query")]

        except Exception as e:
            logger.error(f"Get similar questions error: {e}")
            return []

    def get_historical_insights(self, query: str, user_id: str) -> str:
        """Get historical insights and patterns from user's research.

        Args:
            query: Current query
            user_id: User ID

        Returns:
            Formatted string with historical insights
        """
        try:
            sessions = self.get_user_memory(user_id, limit=5)

            if not sessions:
                return ""

            insights = "## Historical Context from Your Research:\n"
            insights += f"- Total research sessions: {len(sessions)}\n"

            # Calculate average quality score
            avg_quality = sum(s.quality_score for s in sessions) / len(sessions)
            insights += f"- Average quality score: {avg_quality:.2f}/1.0\n"

            # Find most researched topics
            topics = {}
            for session in sessions:
                # Simple topic extraction from query
                words = session.query.lower().split()
                for word in words:
                    if len(word) > 4:  # Filter out small words
                        topics[word] = topics.get(word, 0) + 1

            if topics:
                top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:3]
                insights += f"- Frequent topics: {', '.join([t[0] for t in top_topics])}\n"

            insights += "\nUse this context to provide more relevant and consistent answers.\n"

            return insights

        except Exception as e:
            logger.error(f"Get historical insights error: {e}")
            return ""
