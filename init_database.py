"""
Database Initialization Script
================================
Creates all tables and optionally seeds a test user.

Usage:
    python init_database.py              # Create tables only
    python init_database.py --seed       # Create tables + seed test user
    python init_database.py --reset      # Drop all tables, recreate, and seed
"""

import sys
import os
import logging

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("init_database")


def main():
    from config.settings import settings
    from auth.models import Base, User
    from auth import database as db_module
    from auth.password_manager import PasswordManager

    # ── Validate required config ────────────────────────
    if not settings.database_url:
        logger.error("DATABASE_URL is not set in .env — cannot initialize database.")
        logger.error("Example: DATABASE_URL=sqlite:///./research_agent.db")
        sys.exit(1)

    if not settings.jwt_secret or len(settings.jwt_secret) < 32:
        logger.error("JWT_SECRET is missing or too short (min 32 chars) in .env")
        sys.exit(1)

    # ── Parse flags ─────────────────────────────────────
    do_seed = "--seed" in sys.argv
    do_reset = "--reset" in sys.argv

    logger.info(f"Database URL: {settings.database_url}")

    # ── Reset (drop all) ───────────────────────────────
    if do_reset:
        logger.warning("⚠️  --reset flag detected: dropping all tables!")
        if not db_module.init_db():
            logger.error("Failed to connect to database")
            sys.exit(1)

        Base.metadata.drop_all(bind=db_module.engine)
        logger.info("All tables dropped.")

    # ── Create tables ──────────────────────────────────
    if not db_module.init_db():
        logger.error("Database initialization failed!")
        sys.exit(1)

    logger.info("✅ All tables created successfully:")
    for table_name in Base.metadata.tables:
        logger.info(f"   • {table_name}")

    # ── Seed test user ─────────────────────────────────
    if do_seed or do_reset:
        db = db_module.SessionLocal()
        try:
            existing = db.query(User).filter_by(username="admin").first()
            if existing:
                logger.info(f"Test user 'admin' already exists (id: {existing.user_id})")
            else:
                pm = PasswordManager()
                test_user = User(
                    username="admin",
                    email="admin@research-agent.local",
                    password_hash=pm.hash_password("admin123!"),
                    is_active=True,
                )
                db.add(test_user)
                db.commit()
                db.refresh(test_user)
                logger.info(f"✅ Test user created:")
                logger.info(f"   Username: admin")
                logger.info(f"   Password: admin123!")
                logger.info(f"   Email:    admin@research-agent.local")
                logger.info(f"   User ID:  {test_user.user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to seed test user: {e}")
        finally:
            db.close()

    logger.info("")
    logger.info("🚀 Database is ready! You can now run: python main.py")


if __name__ == "__main__":
    main()
