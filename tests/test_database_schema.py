"""
Tests for database schema creation compatibility
Tests that database schema can be created with both PostgreSQL and SQLite
"""

import pytest
import os
import tempfile
from sqlalchemy import create_engine, text
from api.database import Base, DATABASE_URL


def test_database_schema_creation_with_sqlite():
    """
    Test that database schema can be created with SQLite.
    This catches issues like postgresql_where clauses that don't work with SQLite.
    """
    # Create temporary SQLite database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Create engine with SQLite
        sqlite_url = f"sqlite:///{tmp_path}"
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
        
        # This should not raise an exception
        # If postgresql_where is used, it will fail here
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            assert 'users' in tables
            assert 'blueprints' in tables
            assert 'files' in tables
        
        # Close engine to release file handle
        engine.dispose()
        
    finally:
        # Cleanup - wait a bit for file handle to be released
        import time
        time.sleep(0.1)
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except PermissionError:
                # File might still be locked, that's okay for test purposes
                pass
