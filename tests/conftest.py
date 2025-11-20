"""Pytest configuration and fixtures."""

import pytest
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import Settings, get_settings
from app.db import Base, get_engine, get_session_factory
from app.models import Lead, OptOut, OutreachHistory, Campaign

# Set test environment variables
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["EMAIL_FROM"] = "test@example.com"
os.environ["BUSINESS_ADDRESS"] = "123 Test Street, Test City, TC 12345"
os.environ["DRY_RUN_MODE"] = "true"
os.environ["APPROVAL_MODE"] = "true"


@pytest.fixture(scope="session")
def test_settings():
    """Provide test settings."""
    return get_settings()


@pytest.fixture(scope="function")
def test_db():
    """Provide test database session with clean state."""
    # Create test database engine
    engine = create_engine("sqlite:///./test.db", connect_args={"check_same_thread": False})
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    yield TestingSessionLocal
    
    # Clean up
    Base.metadata.drop_all(bind=engine)
    
    # Remove test database file
    import os
    if os.path.exists("./test.db"):
        os.remove("./test.db")
