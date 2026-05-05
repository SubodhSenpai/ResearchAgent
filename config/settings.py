import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Settings:
    open_api_key: str = os.getenv('OPENAI_API_KEY', '')
    tavily_api_key: str = os.getenv('TAVILY_API_KEY', '')
    model_name: str = os.getenv('MODEL_NAME', 'gpt-4o-mini')
    temperature: float = 0.3
    max_iterations: int = 5
    quality_threshold: float = 0.7
    chroma_persist_dir: str = './chroma_db'

    def validate(self):
        if not self.open_api_key:
            raise ValueError('OPEN_API_KEY is required')
        if not self.tavily_api_key:
            raise ValueError('TAVILY_API_KEY is required')

settings = Settings()