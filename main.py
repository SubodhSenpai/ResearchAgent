import os
import sys
import logging
import signal
import subprocess
import threading
import time
import urllib.request
import uvicorn
from config.settings import settings
from dotenv import load_dotenv
from api.routes import app
from auth.database import init_db, close_db  

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt = "%Y-%m-%d %H-%M-%S",
)
logger = logging.getLogger("main")


def _validate_env() -> None:
    missing: list[str] = []

    if not settings.model_name.strip():
        missing.append(" MODEL_NAME (e.g. gemini-2.5-pro or gpt-4o-mini)")

    if settings.uses_google_llm():
        if not settings.google_api_key:
            missing.append(
                " GOOGLE_API_KEY or GEMINI_API_KEY (required when MODEL_NAME is a Gemini model)"
            )
    else:
        if not settings.open_api_key:
            missing.append(" OPENAI_API_KEY (required when MODEL_NAME is an OpenAI model)")

    # Web search uses Tavily when not on Gemini; OpenAI runs need Tavily.
    if not settings.uses_google_llm() and not settings.tavily_api_key:
        missing.append(
            " TAVILY_API_KEY (required for web search when using OpenAI models)"
        )

    # Authentication & Database
    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        missing.append(" JWT_SECRET (must be at least 32 characters)")

    if not settings.database_url:
        missing.append(" DATABASE_URL (e.g., postgresql://user:password@localhost/research_agent_db)")

    if missing:
        logger.error("Missing required configuration:\n%s", "\n".join(missing))
        logger.error("Create a .env file or export them before starting.")
        sys.exit(1)

def _ui_path() -> str:
    path = os.path.join(os.path.dirname(__file__), "ui", "app.py")
    if not os.path.exists(path):
        logger.error("Streamlit app not found at: %s", path)
        sys.exit(1)
    return path

def _wait_for_api(host: str, port: int, timeout: int = 3) -> bool:
    url = f"http://{'localhost' if host == '0.0.0.0' else host}:{port}/health"
    deadline = time.time() + timeout
    logger.info("Waiting for API to be ready at %s ...", url)


    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)

    return False

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
    logger.info("Database: %s", settings.database_url.split("@")[1] if "@" in settings.database_url else "configured")

    try:
        uvicorn.run("api.routes:app", host=host, port=port, reload=reload, log_level="info")
    finally:
        close_db()


def run_ui() -> None:
    logger.info("Starting Streamlit UI - http://%s:%s", os.getenv("UI_HOST", "localhost"), os.getenv("UI_PORT", "8001"))
    logger.info("Connecting to API at %s", os.getenv("API_URL", "http://localhost:8000"))


    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            _ui_path(),
            "--server.port",
            os.getenv("UI_PORT", "8001"),
            "--server.address",
            os.getenv("UI_HOST", "localhost"),
        ],
        check=True,
    )


def run_both() -> None:
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))

    os.environ["RELOAD"] = "false"
    logger.info("MODE=both: starting FastAPI + Streamlit together")

    api_thread = threading.Thread(target=run_api, daemon=True, name="fastapi")
    api_thread.start()

    if not _wait_for_api(host, port, timeout=30):
        logger.error("API did not become healthy within 30 seconds - aborting.")
        sys.exit(1)

    logger.info("API is healthy. Launching Streamlit now. ")

    if not os.getenv("API_URL"): os.environ["API_URL"] = f"http://localhost:{port}"

    ui_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", _ui_path(),
        "--server.port", os.getenv("UI_PORT", "8001"), "--server.address", os.getenv("UI_HOST", "localhost"),
    ])

    def _shutdown(sig, frame):
        logger.info("Shutting down (signal %d)...", sig)
        ui_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    ui_proc.wait()
    logger.info("Streamlit exited. Shutting down API thread.")


if __name__ == "__main__":
    try:
        load_dotenv()
        logger.info("Loaded environment from .env")
    except ImportError:
        pass

    _validate_env()

    # Default to 'api' for Railway/production. Set MODE=both for local development
    mode = os.getenv("MODE", "api").lower()

    match mode:
        case "api":
            run_api()
        case "ui":
            run_ui()
        case "both":
            run_both()
        case _:
            logger.error("Unknown MODE=%r - choose 'api' , 'ui', or 'both'", mode)
            sys.exit(1)