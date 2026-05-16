import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

class ResearchLogger:
    """
    Dedicated logger for research sessions.
    Captures agent steps, LLM prompts, and retrieval results.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.log_dir = Path("logs") / "research"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{session_id}.jsonl"

    def log_step(self, agent_name: str, step_type: str, data: Dict[str, Any]):
        """
        Logs a single step in the research process.
        step_type can be: 'input', 'prompt', 'llm_response', 'retrieval', 'error'
        """
        from config.settings import settings
        if not settings.enable_research_logging:
            return

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent_name,
            "type": step_type,
            "data": data
        }
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass # Silent failure for logging

    @staticmethod
    def get_session_logger(session_id: str):
        return ResearchLogger(session_id)

def trace_agent(agent_name: str):
    """Decorator to automatically log agent inputs and outputs."""
    def decorator(func):
        def wrapper(self, state: Dict[str, Any], *args, **kwargs):
            session_id = state.get("session_id", "unknown")
            logger = ResearchLogger(session_id)
            
            logger.log_step(agent_name, "input", {"state_keys": list(state.keys())})
            
            try:
                result = func(self, state, *args, **kwargs)
                logger.log_step(agent_name, "output", {"next_agent": result.get("_next")})
                return result
            except Exception as e:
                logger.log_step(agent_name, "error", {"detail": str(e)})
                raise e
        return wrapper
    return decorator
