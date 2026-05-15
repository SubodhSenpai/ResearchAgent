import os
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _google_api_from_env() -> str:
    return (os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip()


@dataclass
class Settings:
    # LLM & Search Configuration
    open_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip())
    google_api_key: str = field(default_factory=_google_api_from_env)
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", "").strip())
    model_name: str = field(default_factory=lambda: os.getenv("MODEL_NAME", "").strip())
    temperature: float = 0.3
    max_iterations: int = 5
    quality_threshold: float = 0.7

    # Authentication & JWT
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "").strip())
    jwt_algorithm: str = field(default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256").strip())
    jwt_expiry: int = field(default_factory=lambda: int(os.getenv("JWT_EXPIRY", "86400")))

    # Database Configuration
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "").strip())

    # Vector & Memory Storage
    chroma_persist_dir: str = field(
        default_factory=lambda: os.getenv("CHROMA_PERSIST_DIR", "./chroma_db").strip()
    )
    google_embedding_model: str = field(
        default_factory=lambda: os.getenv(
            "GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-001"
        ).strip()
    )
    openai_embedding_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    )

    # PageIndex RAG Configuration (self-hosted, no API key required)
    pageindex_workspace: str = field(
        default_factory=lambda: os.getenv("PAGEINDEX_WORKSPACE", "./pageindex_data").strip()
    )
    pageindex_model: str = field(
        default_factory=lambda: os.getenv("PAGEINDEX_MODEL", "").strip()
    )

    @cached_property
    def chroma_sessions_dir(self) -> str:
        """Session memory uses its own folder so it does not share a Chroma client with LangChain RAG."""
        base = self.chroma_persist_dir
        override = os.getenv("CHROMA_SESSIONS_DIR", "").strip()
        return override if override else os.path.normpath(os.path.join(base, "sessions"))

    @cached_property
    def chroma_rag_dir(self) -> str:
        """RAG / document vector store (LangChain Chroma) — separate client settings from SessionMemory."""
        base = self.chroma_persist_dir
        override = os.getenv("CHROMA_RAG_DIR", "").strip()
        return override if override else os.path.normpath(os.path.join(base, "rag"))

    @cached_property
    def pageindex_workspace_path(self) -> str:
        """PageIndex workspace directory for hierarchical document indexing with OCR."""
        return self.pageindex_workspace

    def uses_google_llm(self) -> bool:
        """
        Prefer LLM_PROVIDER when set. Otherwise infer from MODEL_NAME:
        - names starting with or containing 'gemini' -> Google
        - otherwise -> OpenAI (e.g. gpt-4o, o1, o3)
        """
        override = os.getenv("LLM_PROVIDER", "").strip().lower()
        if override in ("google", "gemini"):
            return True
        if override in ("openai",):
            return False
        name = (self.model_name or "").lower().strip()
        if not name:
            return False
        return name.startswith("gemini") or "/gemini" in name

    def get_embeddings(self) -> Any:
        """Embedding model appropriate for the current chat provider (not the chat model id)."""
        if self.uses_google_llm():
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            kwargs: dict[str, Any] = {"model": self.google_embedding_model}
            if self.google_api_key:
                kwargs["google_api_key"] = self.google_api_key
            return GoogleGenerativeAIEmbeddings(**kwargs)
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=self.openai_embedding_model,
            api_key=self.open_api_key or None,
        )

    def validate(self) -> None:
        if not self.model_name:
            raise ValueError("MODEL_NAME is required")
        if self.uses_google_llm():
            if not self.google_api_key:
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY is required for Gemini models")
        else:
            if not self.open_api_key:
                raise ValueError("OPENAI_API_KEY is required for OpenAI models")

        # JWT Configuration
        if not self.jwt_secret or len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        if not self.jwt_algorithm:
            raise ValueError("JWT_ALGORITHM is required")
        if not self.jwt_expiry or self.jwt_expiry <= 0:
            raise ValueError("JWT_EXPIRY must be a positive integer")

        # Database Configuration
        if not self.database_url:
            raise ValueError("DATABASE_URL is required for production")

        # Tavily is checked in main only when web search needs it (OpenAI path).


settings = Settings()
