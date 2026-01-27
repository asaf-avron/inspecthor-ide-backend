"""
Database models and initialization for Guardian Gateway
Uses SQLAlchemy ORM with PostgreSQL for UUID support and cascades
"""

from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, Index,
    ForeignKey, Enum, func, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os
import hashlib
import uuid

Base = declarative_base()


class User(Base):
    """
    Represents a user account authenticated via GitHub OAuth.
    Users own projects and have rate limiting applied.
    """
    __tablename__ = 'users'
    
    user_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    github_id = Column(Integer, nullable=False)
    github_login = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    
    # Encrypted GitHub OAuth tokens
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # User tier and rate limiting
    tier = Column(
        Enum('free', 'pro', 'team', name='user_tier_enum'),
        nullable=False,
        default='free'
    )
    verification_credits = Column(Integer, nullable=False, default=10)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    projects = relationship(
        "Project",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    installations = relationship(
        "Installation",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    __table_args__ = (
        Index('ix_users_github_id', github_id, unique=True),
        Index('ix_users_github_login', github_login),
        Index('ix_users_created_at', created_at.desc()),
    )


class Project(Base):
    """
    Represents a project grouping multiple files.
    Projects can be owned by users (authenticated) or API keys (anonymous/legacy).
    """
    __tablename__ = 'projects'
    
    project_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Owner can be either a user or an API key (for backward compatibility)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    api_key_hash = Column(String(64), nullable=True, index=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User", back_populates="projects")
    files = relationship(
        "File",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    # Indexes and constraints
    __table_args__ = (
        # Unique constraint: name is unique per user
        Index(
            'ix_projects_user_id_name_lower',
            user_id,
            func.lower(name),
            unique=True,
            postgresql_where=Column('user_id').isnot(None)
        ),
        # Unique constraint: name is unique per API key (legacy)
        Index(
            'ix_projects_api_key_hash_name_lower',
            api_key_hash,
            func.lower(name),
            unique=True,
            postgresql_where=Column('api_key_hash').isnot(None)
        ),
        # Index for sorting by updated_at
        Index('ix_projects_updated_at', updated_at.desc()),
    )


class File(Base):
    """
    Represents a saved specification or Dafny file.
    Files belong to a project and are associated with API keys for access control.
    """
    __tablename__ = 'files'
    
    file_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.project_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    filename = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(
        Enum('md', 'dfy', 'unit', name='file_type_enum'),
        nullable=False
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    project = relationship("Project", back_populates="files")
    
    # Unit links relationships
    unit_links_as_root = relationship(
        "UnitLink",
        foreign_keys="[UnitLink.root_file_id]",
        cascade="all, delete-orphan",
        back_populates="root_file"
    )
    unit_links_as_unit = relationship(
        "UnitLink",
        foreign_keys="[UnitLink.unit_file_id]",
        cascade="all, delete-orphan",
        back_populates="unit_file"
    )
    unit_links_as_dafny = relationship(
        "UnitLink",
        foreign_keys="[UnitLink.dafny_file_id]",
        cascade="all, delete-orphan",
        back_populates="dafny_file"
    )
    
    # Unique constraint: filename is unique per project
    __table_args__ = (
        Index('ix_files_project_id_filename', project_id, filename, unique=True),
    )


class UnitLink(Base):
    """
    Represents a link between a root specification file, a unit file, and its Dafny file.
    Used for the deconstruction feature to maintain traceability.
    """
    __tablename__ = 'unit_links'
    
    link_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    root_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False
    )
    unit_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False
    )
    dafny_file_id = Column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False
    )
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    verification_status = Column(
        Enum('unknown', 'verified', 'failed', 'pending', name='verification_status_enum'),
        nullable=False,
        default='unknown'
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    root_file = relationship("File", foreign_keys=[root_file_id], back_populates="unit_links_as_root")
    unit_file = relationship("File", foreign_keys=[unit_file_id], back_populates="unit_links_as_unit")
    dafny_file = relationship("File", foreign_keys=[dafny_file_id], back_populates="unit_links_as_dafny")


class Installation(Base):
    """
    Represents a GitHub App installation on a user's account or organization.
    Stores installation credentials and metadata.
    """
    __tablename__ = 'installations'
    
    installation_id = Column(
        Integer,
        primary_key=True  # GitHub's installation ID
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # GitHub metadata
    account_login = Column(String(255), nullable=False)  # GitHub username/org
    account_type = Column(String(50), nullable=False)  # "User" or "Organization"
    account_id = Column(Integer, nullable=False)
    
    # Installation status
    suspended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    installed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User")
    repositories = relationship(
        "Repository",
        back_populates="installation",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    __table_args__ = (
        Index('ix_installations_user_id', user_id),
        Index('ix_installations_account_login', account_login),
    )


class Repository(Base):
    """
    Represents a GitHub repository connected to InSpecThor.
    Links to projects for syncing specs and code.
    """
    __tablename__ = 'repositories'
    
    repository_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # GitHub metadata
    github_repo_id = Column(Integer, nullable=False)
    installation_id = Column(
        Integer,
        ForeignKey('installations.installation_id', ondelete='CASCADE'),
        nullable=False
    )
    
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(512), nullable=False)  # "owner/repo"
    default_branch = Column(String(255), nullable=False, default='main')
    
    # InSpecThor project link
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.project_id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Sync status
    last_synced_at = Column(DateTime, nullable=True)
    sync_status = Column(
        Enum('never', 'syncing', 'synced', 'error', name='sync_status_enum'),
        nullable=False,
        default='never'
    )
    
    # Configuration
    config_json = Column(Text, nullable=True)  # .inspecthor.json contents
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    installation = relationship("Installation", back_populates="repositories")
    project = relationship("Project")
    anchors = relationship(
        "Anchor",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    __table_args__ = (
        Index('ix_repositories_github_repo_id', github_repo_id, unique=True),
        Index('ix_repositories_installation_id', installation_id),
        Index('ix_repositories_owner_name', owner, name),
    )


class Anchor(Base):
    """
    Represents a code anchor binding a function to a specification.
    Anchors can be manually added via decorators or auto-detected.
    """
    __tablename__ = 'anchors'
    
    anchor_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Project link
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey('projects.project_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Repository link (if GitHub-linked)
    repository_id = Column(
        UUID(as_uuid=True),
        ForeignKey('repositories.repository_id', ondelete='CASCADE'),
        nullable=True
    )
    
    # Location in code
    file_path = Column(String(512), nullable=False)  # "src/auth/token.py"
    function_name = Column(String(255), nullable=False)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    
    # Binding to specification
    spec_id = Column(String(255), nullable=False)  # "REQ-101"
    contract_ref = Column(String(512), nullable=False)  # "specs/auth.dfy::ValidateToken"
    
    # Verification status
    last_verified_at = Column(DateTime, nullable=True)
    verification_status = Column(
        Enum('unknown', 'verified', 'failed', 'pending', name='anchor_status_enum'),
        nullable=False,
        default='unknown'
    )
    proof_receipt_hash = Column(String(64), nullable=True)
    
    # Metadata
    language = Column(
        Enum('python', 'typescript', 'javascript', name='anchor_language_enum'),
        nullable=False
    )
    auto_detected = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    project = relationship("Project")
    repository = relationship("Repository", back_populates="anchors")
    proof_receipts = relationship(
        "ProofReceipt",
        back_populates="anchor",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    __table_args__ = (
        Index('ix_anchors_project_id', project_id),
        Index('ix_anchors_repository_id', repository_id),
        Index('ix_anchors_spec_id', spec_id),
        Index('ix_anchors_verification_status', verification_status),
    )


class ProofReceipt(Base):
    """
    Represents a cached verification result (proof receipt).
    Used to skip redundant verification when code/contract unchanged.
    """
    __tablename__ = 'proof_receipts'
    
    receipt_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Anchor link
    anchor_id = Column(
        UUID(as_uuid=True),
        ForeignKey('anchors.anchor_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Content hashes for cache invalidation
    content_hash = Column(String(64), nullable=False)  # SHA-256 of execution slice
    contract_hash = Column(String(64), nullable=False)  # SHA-256 of Dafny contract
    
    # Verification result
    status = Column(
        Enum('verified', 'failed', name='receipt_status_enum'),
        nullable=False
    )
    dafny_output = Column(Text, nullable=False)  # Full verifier output
    counterexample = Column(Text, nullable=True)  # JSON if failed
    
    # Provenance
    verified_by = Column(
        Enum('ide', 'webhook', 'manual', name='verified_by_enum'),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete='SET NULL'),
        nullable=True
    )
    commit_sha = Column(String(40), nullable=True)  # Git commit SHA if webhook
    
    # Timing
    verification_time_ms = Column(Integer, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # Auto-expire old receipts
    
    # Relationships
    anchor = relationship("Anchor", back_populates="proof_receipts")
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_receipts_anchor_id', anchor_id),
        Index('ix_receipts_content_contract_hash', content_hash, contract_hash),
        Index('ix_receipts_status', status),
        Index('ix_receipts_expires_at', expires_at),
    )


# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://guardian:guardian_dev_password@localhost:5432/guardian_gateway')

# Create engine with connection pooling for PostgreSQL
if DATABASE_URL.startswith('sqlite'):
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL connection pooling
    connect_args = {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set to True for SQL debugging
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initialize database tables.
    For development: drops existing tables and recreates with new schema.
    For production: use Alembic migrations instead.
    """
    import logging
    from sqlalchemy import text
    logger = logging.getLogger(__name__)
    
    # Check if we're in development mode (drop and recreate)
    # In production, use Alembic migrations: `alembic upgrade head`
    drop_existing = os.getenv("DROP_EXISTING_TABLES", "true").lower() == "true"
    
    if drop_existing:
        # Drop all existing tables and indexes to avoid schema conflicts
        logger.info("Dropping existing tables (dev mode)...")
        
        # For PostgreSQL, use CASCADE to drop everything
        if DATABASE_URL and 'postgresql' in DATABASE_URL:
            with engine.connect() as conn:
                try:
                    # Drop all indexes that might conflict
                    result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE schemaname = 'public' 
                        AND indexname LIKE 'ix_%'
                    """))
                    indexes = [row[0] for row in result]
                    for idx in indexes:
                        conn.execute(text(f"DROP INDEX IF EXISTS {idx} CASCADE"))
                    conn.commit()
                    logger.info(f"Dropped {len(indexes)} existing indexes")
                except Exception as e:
                    logger.warning(f"Error dropping indexes: {e}")
                    conn.rollback()
                
                # Drop all tables with CASCADE
                Base.metadata.drop_all(bind=engine)
                
                try:
                    # Drop enum types if they exist
                    conn.execute(text("DROP TYPE IF EXISTS user_tier_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS file_type_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS verification_status_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS sync_status_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS anchor_status_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS anchor_language_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS receipt_status_enum CASCADE"))
                    conn.execute(text("DROP TYPE IF EXISTS verified_by_enum CASCADE"))
                    conn.commit()
                    logger.info("Dropped existing enum types")
                except Exception as e:
                    logger.warning(f"Error dropping enum types: {e}")
                    conn.rollback()
        else:
            # For SQLite or other databases
            Base.metadata.drop_all(bind=engine)
    
    # Create all tables with new schema
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")


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
