from abc import ABC, abstractmethod
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from config.settings import settings


class BaseAgent(ABC):
    '''
    Abstracct base for all reearch agents. Every agent has a name, an LLM, and a system prompt.
    Every agent implements the run() method.
    '''

    def __init__(self, name:str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = ChatOpenAI(
            model = settings.model_name,
            temperature = settings.temperature,
            api_key = settings.open_api_key
        )
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

    def _log(self, message:str):
        self._call_count += 1
        print(f'[{self.name}] Call #{self._call_count}: {message}')

    def __repr__(self):
        return f'{self.__class__.__name__}(name={self.name!r}, calls={self._call_count})'