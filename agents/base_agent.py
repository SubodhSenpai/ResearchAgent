from abc import ABC, abstractmethod
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from utils.research_logger import ResearchLogger
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    '''
    Abstracct base for all reearch agents. Every agent has a name, an LLM, and a system prompt.
    Every agent implements the run() method.
    '''

    def __init__(self, name:str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.logger = logging.getLogger(f"agent.{name}")
        
        # Use Gemini for all agents
        try:
            self.llm = ChatGoogleGenerativeAI(
                model=settings.model_name,
                temperature=settings.temperature,
                google_api_key=settings.gemini_api_key or None,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini for {name}: {e}")
            self.llm = None
        
        self._call_count = 0

    @abstractmethod
    def run(self, state:dict) -> dict:
        '''
        Execute agent logic. Must return updated state.
        '''
        pass

    def _build_chain(self, human_template: str):
        '''
        Build a LCEL chain for this agent.
        '''
        prompt = ChatPromptTemplate.from_messages([
            ('system', self.system_prompt),
            ('user', human_template)
        ])
        return prompt | self.llm

    def _log(self, message: str):
        self.logger.info(f"[{self.name}] {message}")

    def trace(self, session_id: str, step_type: str, data: dict):
        """Log a trace event for the current session."""
        if session_id and session_id != "unknown":
            ResearchLogger(session_id).log_step(self.name, step_type, data)

    def __repr__(self):
        return f'{self.__class__.__name__}(name={self.name!r}, calls={self._call_count})'