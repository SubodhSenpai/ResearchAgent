import logging
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from memory.memory_manager import MemoryManager
from memory.session_memory import SessionMemory

logger = logging.getLogger(__name__)


class MemoryRetrievalTool:
    """Tool for retrieving user memory and past research context for agents."""

    def __init__(self, user_id: str, db: DBSession, session_memory: Optional[SessionMemory] = None):
        self.user_id = user_id
        self.db = db
        self.memory_manager = MemoryManager(db, session_memory)
        self.session_memory = session_memory

    def get_user_memory(self, k: int = 5) -> str:
        """Get user's recent successful research formatted for agent context.

        Args:
            k: Number of past sessions to retrieve

        Returns:
            Formatted string of user's recent research
        """
        try:
            sessions = self.memory_manager.get_user_memory(self.user_id, limit=k)
            return self.memory_manager.format_user_memory(sessions, limit=k)

        except Exception as e:
            logger.error(f"Error getting user memory: {e}")
            return ""

    def get_session_history(self, session_id: str) -> str:
        """Get full chat history for a session formatted for context.

        Args:
            session_id: Session ID

        Returns:
            Formatted string of chat history
        """
        try:
            history = self.memory_manager.get_history(session_id)

            if not history:
                return "No chat history found for this session."

            context = f"## Chat History for Session {session_id}:\n\n"
            for msg in history:
                msg_type = "You" if msg.message_type == "user" else "Assistant"
                context += f"**{msg_type}:** {msg.content}\n"

            return context

        except Exception as e:
            logger.error(f"Error getting session history: {e}")
            return ""

    def find_similar_past_queries(self, query: str, k: int = 3) -> str:
        """Find similar questions the user has asked before.

        Args:
            query: Current query
            k: Number of similar queries to find

        Returns:
            Formatted string with similar past queries
        """
        try:
            similar_sessions = self.memory_manager.search_memory(query, self.user_id, k)

            if not similar_sessions:
                return "No similar past research found."

            context = f"## Similar Past Research:\n\n"
            for i, session in enumerate(similar_sessions, 1):
                context += f"**{i}. Query:** {session.get('query', 'N/A')}\n"
                context += f"   **Answer:** {session.get('answer', 'N/A')[:200]}...\n"
                context += (
                    f"   **Quality:** {session.get('quality_score', 0):.2f}/1.0\n"
                )
                context += f"   **Similarity:** {session.get('similarity', 0):.2%}\n\n"

            return context

        except Exception as e:
            logger.error(f"Error finding similar queries: {e}")
            return ""

    def retrieve_with_embeddings(self, query_vector: Optional[List] = None, k: int = 4) -> str:
        """Retrieve similar research using semantic embeddings.

        Args:
            query_vector: Query embedding vector (optional)
            k: Number of results

        Returns:
            Formatted string of semantically similar research
        """
        try:
            # For now, use text-based search since we don't have direct vector access
            # In production, would use actual embedding vectors
            similar = self.memory_manager.search_memory(
                query="",  # Would use query_vector here
                user_id=self.user_id,
                k=k,
            )

            if not similar:
                return "No semantically similar research found."

            context = "## Semantically Similar Research:\n\n"
            for i, result in enumerate(similar, 1):
                context += f"**{i}. {result.get('query', 'N/A')[:60]}...**\n"
                context += f"   Similarity Score: {result.get('similarity', 0):.2%}\n"

            return context

        except Exception as e:
            logger.error(f"Error retrieving with embeddings: {e}")
            return ""

    def get_relevant_context(self, query: str, context_type: str = "all") -> str:
        """Get relevant context for the current query.

        Args:
            query: Current query
            context_type: "all", "similar", "recent", or "insights"

        Returns:
            Formatted context string
        """
        try:
            if context_type == "similar":
                return self.find_similar_past_queries(query, k=3)

            elif context_type == "recent":
                return self.get_user_memory(k=3)

            elif context_type == "insights":
                return self.memory_manager.get_historical_insights(query, self.user_id)

            else:  # "all"
                context = ""
                context += self.get_user_memory(k=2) + "\n\n"
                context += self.find_similar_past_queries(query, k=2) + "\n\n"
                context += self.memory_manager.get_historical_insights(query, self.user_id)
                return context

        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return ""

    def get_researcher_context(self, query: str) -> str:
        """Get context specifically for the Researcher agent.

        Args:
            query: Current research query

        Returns:
            Formatted context for researcher
        """
        try:
            context = "## Previous Research Context:\n\n"

            # Get similar past queries
            similar = self.memory_manager.search_memory(query, self.user_id, k=2)
            if similar:
                context += "**Previously researched similar topics:**\n"
                for s in similar:
                    context += f"- {s.get('query', 'N/A')}\n"
                context += "\n"

            # Get sources and facts from past research
            past_sessions = self.memory_manager.get_user_memory(self.user_id, limit=2)
            if past_sessions:
                context += "**Key facts from your past research:**\n"
                for session in past_sessions:
                    if session.final_answer:
                        context += f"- From '{session.query[:40]}...': "
                        context += f"{session.final_answer[:100]}...\n"

            return context

        except Exception as e:
            logger.error(f"Error getting researcher context: {e}")
            return ""

    def get_analyst_context(self, query: str) -> str:
        """Get context specifically for the Analyst agent.

        Args:
            query: Current research query

        Returns:
            Formatted context for analyst
        """
        try:
            context = "## Analysis Context from Past Research:\n\n"

            # Get past analyses on similar topics
            similar = self.memory_manager.search_memory(query, self.user_id, k=3)
            if similar:
                context += "**Past analyses on similar topics:**\n"
                for i, s in enumerate(similar, 1):
                    context += f"{i}. Query: {s.get('query', 'N/A')[:50]}...\n"
                    context += f"   Quality: {s.get('quality_score', 0):.2f}/1.0\n"
                context += "\n"

            # Get user's analysis preferences from historical patterns
            insights = self.memory_manager.get_historical_insights(query, self.user_id)
            if insights:
                context += "**Your analysis patterns:**\n"
                context += insights

            return context

        except Exception as e:
            logger.error(f"Error getting analyst context: {e}")
            return ""

    def get_supervisor_context(self, query: str) -> str:
        """Get context specifically for the Supervisor agent.

        Args:
            query: Current research query

        Returns:
            Formatted context for supervisor
        """
        try:
            context = "## Supervision Context:\n\n"

            # Check if user has asked similar questions before
            similar_questions = self.memory_manager.get_similar_questions(query, self.user_id, k=2)
            if similar_questions:
                context += "**Similar questions you've asked before:**\n"
                for q in similar_questions:
                    context += f"- {q}\n"
                context += "\n"

            # Get user's research quality baseline
            past_sessions = self.memory_manager.get_user_memory(self.user_id, limit=5)
            if past_sessions:
                avg_quality = (
                    sum(s.quality_score for s in past_sessions) / len(past_sessions)
                )
                context += f"**Your research quality baseline:** {avg_quality:.2f}/1.0\n"
                context += f"**Total research sessions:** {len(past_sessions)}\n"

            return context

        except Exception as e:
            logger.error(f"Error getting supervisor context: {e}")
            return ""
