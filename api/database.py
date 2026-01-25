"""
Database models and initialization for Guardian Gateway
Uses SQLAlchemy ORM with SQLite (easily upgradeable to PostgreSQL)
"""

from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
import hashlib

Base = declarative_base()


class File(Base):
    """
    Represents a saved specification or Dafny file.
    Files are associated with API keys for access control.
    """
    __tablename__ = 'files'
    
    file_id = Column(String(36), primary_key=True)
    api_key_hash = Column(String(64), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(String(20), nullable=False)  # 'markdown' or 'dafny'
    project_id = Column(String(36), nullable=True, index=True)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_api_key_type', 'api_key_hash', 'file_type'),
    )


class Project(Base):
    """
    Represents a project grouping multiple files.
    Future feature for better organization.
    """
    __tablename__ = 'projects'
    
    project_id = Column(String(36), primary_key=True)
    api_key_hash = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./guardian_gateway.db')

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {},
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency for FastAPI to get database session.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage (don't store keys in plaintext).
    Uses SHA-256 for consistent hashing.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()
