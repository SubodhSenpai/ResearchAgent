import os
import sys
import logging
import uvicorn
from config.settings import settings
from dotenv import load_dotenv
from api.routes import app
from auth.database import init_db, close_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H-%M-%S",
)
logger = logging.getLogger("main")


def _validate_env() -> None:
    missing: list[str] = []

    if not settings.model_name.strip():
        missing.append(" MODEL_NAME (e.g. gemini-1.5-flash)")

    if settings.uses_google_llm():
        if not settings.google_api_key:
            missing.append(
                " GOOGLE_API_KEY or GEMINI_API_KEY (required for Gemini)"
            )
    else:
        if not settings.open_api_key:
            missing.append(" OPENAI_API_KEY (required for OpenAI)")

    # Authentication & Database
    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        missing.append(" JWT_SECRET (must be at least 32 characters)")

    if not settings.database_url:
        missing.append(" DATABASE_URL (e.g., postgresql://user:password@localhost/db)")

    if missing:
        logger.error("Missing required configuration:\n%s", "\n".join(missing))
        sys.exit(1)


def run_api() -> None:
    # Initialize database
    if not init_db():
        logger.error("Failed to initialize database")
        sys.exit(1)

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    logger.info("Starting FastAPI - http://%s:%d", host, port)
    provider = "google (Gemini)" if settings.uses_google_llm() else "openai"
    logger.info(
        "Provider: %s | Model: %s | Temperature: %s",
        provider,
        settings.model_name,
        settings.temperature,
    )
    logger.info(
        "Storage: sessions=%s | pageindex=%s",
        settings.chroma_sessions_dir,
        settings.pageindex_workspace_path,
    )

    try:
        uvicorn.run("api.routes:app", host=host, port=port, reload=reload, log_level="info")
    finally:
        close_db()


if __name__ == "__main__":
    load_dotenv()
    logger.info("Loaded environment from .env")
    _validate_env()
    run_api()