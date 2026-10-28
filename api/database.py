"""
Database models and initialization for Inspecthor
Uses SQLAlchemy ORM with PostgreSQL for UUID support and cascades
"""

from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, Index,
    ForeignKey, Enum, func, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, relationship
from datetime import datetime
from typing import Optional
import os
import hashlib
import uuid

class Base(DeclarativeBase):
    pass


class User(Base):
    """
    Represents a user account authenticated via GitHub OAuth.
    Users own projects and have rate limiting applied.
    """
    __tablename__ = 'users'
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    github_id: Mapped[int] = mapped_column(Integer, nullable=False)
    github_login: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Encrypted GitHub OAuth tokens
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # User tier and rate limiting
    tier: Mapped[str] = mapped_column(
        Enum('free', 'pro', 'team', name='user_tier_enum'),
        nullable=False,
        default='free'
    )
    verification_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    blueprints = relationship(
        "Blueprint",
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



class Blueprint(Base):
    """
    Represents a blueprint (formerly project) grouping multiple files.
    Blueprints are backed by a GitHub repository and the Trusted Kernel Architecture.
    """
    __tablename__ = 'blueprints'
    
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # GitHub Integration
    repository_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    repository_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    repository_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    installation_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default='main')
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Brain Architecture - Component Tracking
    component_uuid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)  # UUID for component tracking
    registry_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # Path in .inspecthor/registry.yaml

    # Synchronization State (for AI-Gapped Development)
    sync_status: Mapped[str] = mapped_column(
        Enum('clean', 'dirty', 'verifying', 'error', name='sync_status_enum'),
        nullable=False,
        default='clean'
    )
    spec_hash: Mapped[Optional[str]] = mapped_column(String(71), nullable=True)  # SHA256 hash of spec.md (sha256:...)
    dafny_hash: Mapped[Optional[str]] = mapped_column(String(71), nullable=True)  # SHA256 hash of core.dfy
    last_harmonized: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Last harmonization timestamp

    # Owner can be either a user or an API key (for backward compatibility)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user = relationship("User", back_populates="blueprints")
    files = relationship(
        "File",
        back_populates="blueprint",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    # Indexes and constraints
    __table_args__ = (
        # Unique constraint: name is unique per user
        Index(
            'ix_blueprints_user_id_name_lower',
            user_id,
            func.lower(name),
            unique=True,
            postgresql_where=Column('user_id').isnot(None)
        ),
        # Unique constraint: name is unique per API key (legacy)
        Index(
            'ix_blueprints_api_key_hash_name_lower',
            api_key_hash,
            func.lower(name),
            unique=True,
            postgresql_where=Column('api_key_hash').isnot(None)
        ),
        # Index for sorting by updated_at
        Index('ix_blueprints_updated_at', updated_at.desc()),
        # Index for repository URL lookups
        Index('ix_blueprints_repository_url', repository_url),
    )



class File(Base):
    """
    Represents a saved specification or Dafny file.
    Files belong to a project and are associated with API keys for access control.
    """
    __tablename__ = 'files'
    
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('blueprints.blueprint_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(
        Enum('md', 'dfy', 'unit', name='file_type_enum'),
        nullable=False
    )
    renamed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Track if file was manually renamed
    parent_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # Component directory (None = blueprint root)
    file_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON metadata (traceability, statistics, etc.)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # File size in bytes
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    blueprint = relationship("Blueprint", back_populates="files")
    
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
    
    # Spec-Dafny links relationships
    spec_dafny_links_as_spec = relationship(
        "SpecDafnyLink",
        foreign_keys="[SpecDafnyLink.spec_file_id]",
        cascade="all, delete-orphan",
        back_populates="spec_file"
    )
    spec_dafny_links_as_dafny = relationship(
        "SpecDafnyLink",
        foreign_keys="[SpecDafnyLink.dafny_file_id]",
        cascade="all, delete-orphan",
        back_populates="dafny_file"
    )
    
    # Unique constraint: filename is unique per project
    __table_args__ = (
        Index('ix_files_blueprint_id_filename', blueprint_id, filename, unique=True),
    )


class SpecDafnyLink(Base):
    """
    Links a specification file (.md) to its generated Dafny file (.dfy).
    Used for non-unit specs to maintain the relationship between spec and formal code.
    """
    __tablename__ = 'spec_dafny_links'
    
    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    spec_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    dafny_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    spec_file = relationship("File", foreign_keys=[spec_file_id], back_populates="spec_dafny_links_as_spec")
    dafny_file = relationship("File", foreign_keys=[dafny_file_id], back_populates="spec_dafny_links_as_dafny")


class UnitLink(Base):
    """
    Represents a link between a root specification file, a unit file, and its Dafny file.
    Used for the deconstruction feature to maintain traceability.
    """
    __tablename__ = 'unit_links'
    
    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    root_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False
    )
    unit_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False
    )
    dafny_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('files.file_id', ondelete='CASCADE'),
        nullable=False
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        Enum('unknown', 'verified', 'failed', 'pending', name='verification_status_enum'),
        nullable=False,
        default='unknown'
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
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
    
    installation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True  # GitHub's installation ID
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # GitHub metadata
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)  # GitHub username/org
    account_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "User" or "Organization"
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Installation status
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Timestamps
    installed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
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
    
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # GitHub metadata
    github_repo_id: Mapped[int] = mapped_column(Integer, nullable=False)
    installation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('installations.installation_id', ondelete='CASCADE'),
        nullable=False
    )
    
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)  # "owner/repo"
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default='main')
    
    # InSpecThor blueprint link
    blueprint_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('blueprints.blueprint_id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Sync status
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[str] = mapped_column(
        Enum('never', 'syncing', 'synced', 'error', name='sync_status_enum'),
        nullable=False,
        default='never'
    )
    
    # Configuration
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # .inspecthor.json contents
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    installation = relationship("Installation", back_populates="repositories")
    blueprint = relationship("Blueprint")
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
    
    anchor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Blueprint link
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('blueprints.blueprint_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Repository link (if GitHub-linked)
    repository_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('repositories.repository_id', ondelete='CASCADE'),
        nullable=True
    )
    
    # Location in code
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)  # "src/auth/token.py"
    function_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Binding to specification
    spec_id: Mapped[str] = mapped_column(String(255), nullable=False)  # "REQ-101"
    contract_ref: Mapped[str] = mapped_column(String(512), nullable=False)  # "specs/auth.dfy::ValidateToken"
    
    # Verification status
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        Enum('unknown', 'verified', 'failed', 'pending', name='anchor_status_enum'),
        nullable=False,
        default='unknown'
    )
    proof_receipt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Metadata
    language: Mapped[str] = mapped_column(
        Enum('python', 'typescript', 'javascript', name='anchor_language_enum'),
        nullable=False
    )
    auto_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # Relationships
    blueprint = relationship("Blueprint")
    repository = relationship("Repository", back_populates="anchors")
    proof_receipts = relationship(
        "ProofReceipt",
        back_populates="anchor",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    __table_args__ = (
        Index('ix_anchors_blueprint_id', blueprint_id),
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
    
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    # Anchor link
    anchor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('anchors.anchor_id', ondelete='CASCADE'),
        nullable=False
    )
    
    # Content hashes for cache invalidation
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of execution slice
    contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of Dafny contract
    
    # Verification result
    status: Mapped[str] = mapped_column(
        Enum('verified', 'failed', name='receipt_status_enum'),
        nullable=False
    )
    dafny_output: Mapped[str] = mapped_column(Text, nullable=False)  # Full verifier output
    counterexample: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON if failed
    
    # Provenance
    verified_by: Mapped[str] = mapped_column(
        Enum('ide', 'webhook', 'manual', name='verified_by_enum'),
        nullable=False
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users.user_id', ondelete='SET NULL'),
        nullable=True
    )
    commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # Git commit SHA if webhook
    
    # Timing
    verification_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Auto-expire old receipts
    
    # Relationships
    anchor = relationship("Anchor", back_populates="proof_receipts")
    user = relationship("User")
    
    __table_args__ = (
        Index('ix_receipts_anchor_id', anchor_id),
        Index('ix_receipts_content_contract_hash', content_hash, contract_hash),
        Index('ix_receipts_status', status),
        Index('ix_receipts_expires_at', expires_at),
    )


class LedgerEntry(Base):
    """
    Represents a verification entry in the proof ledger.
    Stores verification history for components in the database
    (in addition to file-based storage in .inspecthor/proof_ledger/).
    """
    __tablename__ = 'ledger_entries'

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Component link
    component_uuid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    blueprint_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('blueprints.blueprint_id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )

    # Verification data
    code_hash: Mapped[str] = mapped_column(String(71), nullable=False)  # sha256:...
    status: Mapped[str] = mapped_column(
        Enum('verified', 'failed', 'pending', 'timeout', 'error', name='ledger_status_enum'),
        nullable=False
    )
    proof_obligations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    dafny_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    dafny_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    verification_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    blueprint = relationship("Blueprint")

    __table_args__ = (
        Index('ix_ledger_component_uuid', component_uuid),
        Index('ix_ledger_blueprint_id', blueprint_id),
        Index('ix_ledger_status', status),
        Index('ix_ledger_created_at', created_at.desc()),
        Index('ix_ledger_component_created', component_uuid, created_at.desc()),
    )


# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://inspecthor:inspecthor_dev_password@localhost:5432/inspecthor')

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
