"""Database connection and session management."""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()

# Global engine and session factory
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        
        # Create engine with connection pooling
        _engine = create_engine(
            str(settings.DATABASE_URL),
            pool_pre_ping=True,  # Verify connections before using
            pool_size=10,
            max_overflow=20,
            echo=settings.LOG_LEVEL == "DEBUG"
        )
        
        # Log connection info (without password)
        logger.info(f"Database engine created")
        
    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    return _SessionLocal


def get_db() -> Session:
    """Get database session (for FastAPI dependency injection)."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Get database session as context manager."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    from app.models import (
        Lead, VerificationResult, OutreachHistory,
        OptOut, ApprovalQueue, Campaign, AuditLog
    )
    
    engine = get_engine()
    
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_db():
    """Drop all database tables (use with caution!)."""
    engine = get_engine()
    
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")


async def check_database_connection() -> bool:
    """Check if database connection is healthy."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
