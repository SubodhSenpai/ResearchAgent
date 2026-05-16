from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session as DBSession
from sqlalchemy.pool import QueuePool, StaticPool
import logging
from config.settings import settings
from .models import Base

logger = logging.getLogger(__name__)

# Database engine
engine = None
SessionLocal = None


def init_db():
    """Initialize database connection and create tables."""
    global engine, SessionLocal

    try:
        db_url = settings.database_url
        if not db_url:
            raise ValueError("DATABASE_URL is not configured")

        is_sqlite = db_url.startswith("sqlite")

        if is_sqlite:
            logger.info(f"Connecting to SQLite database: {db_url}")
            # Ensure the directory exists if it's a file-based SQLite db
            if db_url.startswith("sqlite:///"):
                db_path = db_url.replace("sqlite:///", "")
                import os
                if db_path != ":memory:" and os.path.dirname(db_path):
                    os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI
                poolclass=StaticPool,  # SQLite doesn't support QueuePool well
                echo=False,
            )
            # Enable WAL mode and foreign keys for SQLite
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        else:
            safe_url = db_url.split("@")[1] if "@" in db_url else "configured"
            logger.info(f"Connecting to database: {safe_url}")
            engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Create all tables
        Base.metadata.create_all(bind=engine)

        logger.info("Database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False


def get_db() -> DBSession:
    """Get database session for dependency injection.

    Yields:
        Database session

    Raises:
        RuntimeError: If database not initialized
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def close_db():
    """Close database connection."""
    global engine

    if engine:
        engine.dispose()
        logger.info("Database connection closed")
