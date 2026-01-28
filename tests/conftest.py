"""
Pytest configuration and shared fixtures for Guardian Gateway tests.
"""

import os
import pytest

# CRITICAL: Set test API keys BEFORE importing app
# This ensures APIKeyMiddleware reads the correct allowed keys
os.environ["ALLOWED_API_KEYS"] = "test_api_key_123,test_key_456"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from api.database import Base, get_db, hash_api_key

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Override database dependency
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with test API keys configured"""
    return TestClient(app)


@pytest.fixture
def api_key():
    """Test API key that's in ALLOWED_API_KEYS"""
    return "test_api_key_123"


@pytest.fixture
def api_key_hash(api_key):
    """Hashed API key"""
    return hash_api_key(api_key)


@pytest.fixture
def headers(api_key):
    """Request headers with API key"""
    return {"X-API-Key": api_key}
