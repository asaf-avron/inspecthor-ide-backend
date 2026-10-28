"""
Python models matching Dafny DatabaseModel structure.
These are immutable dataclasses representing the Functional Core state.

See: api/verification/models.dfy :: DatabaseModel
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Any
from enum import Enum


class FileType(Enum):
    """File type enum matching Dafny FileType."""
    MD = "md"
    DFY = "dfy"
    UNIT = "unit"


@dataclass(frozen=True)
class Owner:
    """
    Ownership model matching Dafny Owner union type.
    Immutable: either Authenticated(userId) or Anonymous(apiKeyHash).
    """
    user_id: Optional[str] = None
    api_key_hash: Optional[str] = None
    
    def __post_init__(self):
        """Validate that exactly one ownership type is set."""
        if (self.user_id is None) == (self.api_key_hash is None):
            raise ValueError("Owner must have either user_id OR api_key_hash, not both or neither")
    
    @classmethod
    def authenticated(cls, user_id: str) -> "Owner":
        """Create authenticated owner."""
        return cls(user_id=user_id, api_key_hash=None)
    
    @classmethod
    def anonymous(cls, api_key_hash: str) -> "Owner":
        """Create anonymous owner."""
        return cls(user_id=None, api_key_hash=api_key_hash)
    
    def is_authenticated(self) -> bool:
        """Check if owner is authenticated."""
        return self.user_id is not None
    
    def is_anonymous(self) -> bool:
        """Check if owner is anonymous."""
        return self.api_key_hash is not None


@dataclass(frozen=True)
class File:
    """
    File model matching Dafny File datatype.
    Immutable dataclass representing a file in the system.
    """
    file_id: str
    blueprint_id: str
    filename: str
    content: str
    file_type: FileType
    size_bytes: int
    renamed: bool = False
    
    def __post_init__(self):
        """Validate file size matches content length."""
        if self.size_bytes != len(self.content.encode('utf-8')):
            raise ValueError(f"File size_bytes ({self.size_bytes}) must match content length ({len(self.content.encode('utf-8'))})")


@dataclass(frozen=True)
class Blueprint:
    """
    Blueprint model matching Dafny Blueprint datatype.
    Immutable dataclass representing a blueprint in the system.
    """
    blueprint_id: str
    name: str
    description: str
    owner: Owner
    file_ids: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class SystemState:
    """
    System state snapshot matching Dafny SystemState.
    Immutable snapshot of the entire system state.
    
    This is the "World" passed to every transition function in the Functional Core.
    """
    blueprints: Dict[str, Blueprint] = field(default_factory=dict)
    files: Dict[str, File] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """
        Validate system state invariants matching Dafny ValidState predicate.
        
        Returns:
            True if state is valid, raises ValueError if invalid
        """
        # 1. Relational Integrity: Every file pointed to by a blueprint exists
        for pid, blueprint in self.blueprints.items():
            for fid in blueprint.file_ids:
                if fid not in self.files:
                    raise ValueError(f"Blueprint {pid} references file {fid} that doesn't exist")
        
        # 2. Reverse Integrity: Every file points back to its blueprint
        for fid, file_obj in self.files.items():
            if file_obj.blueprint_id not in self.blueprints:
                raise ValueError(f"File {fid} references blueprint {file_obj.blueprint_id} that doesn't exist")
            
            if fid not in self.blueprints[file_obj.blueprint_id].file_ids:
                raise ValueError(f"File {fid} not in blueprint {file_obj.blueprint_id}.file_ids")
        
        # 3. Size Integrity: File metadata matches content
        for fid, file_obj in self.files.items():
            expected_size = len(file_obj.content.encode('utf-8'))
            if file_obj.size_bytes != expected_size:
                raise ValueError(f"File {fid} size_bytes ({file_obj.size_bytes}) doesn't match content length ({expected_size})")
        
        return True
    
    def with_blueprint(self, blueprint: Blueprint) -> "SystemState":
        """Return new state with blueprint added/updated (immutable update)."""
        new_blueprints = {**self.blueprints, blueprint.blueprint_id: blueprint}
        return SystemState(blueprints=new_blueprints, files=self.files)
    
    def with_file(self, file_obj: File) -> "SystemState":
        """Return new state with file added/updated (immutable update)."""
        new_files = {**self.files, file_obj.file_id: file_obj}
        # Update blueprint's file_ids set
        blueprint = self.blueprints.get(file_obj.blueprint_id)
        if blueprint:
            new_file_ids = blueprint.file_ids | {file_obj.file_id}
            new_blueprint = Blueprint(
                blueprint_id=blueprint.blueprint_id,
                name=blueprint.name,
                description=blueprint.description,
                owner=blueprint.owner,
                file_ids=new_file_ids
            )
            new_blueprints = {**self.blueprints, new_blueprint.blueprint_id: new_blueprint}
        else:
            new_blueprints = self.blueprints
        
        return SystemState(blueprints=new_blueprints, files=new_files)
    
    def without_blueprint(self, blueprint_id: str) -> "SystemState":
        """Return new state with blueprint removed (immutable update)."""
        new_blueprints = {k: v for k, v in self.blueprints.items() if k != blueprint_id}
        # Also remove all files belonging to this blueprint
        new_files = {k: v for k, v in self.files.items() if v.blueprint_id != blueprint_id}
        return SystemState(blueprints=new_blueprints, files=new_files)
    
    def without_file(self, file_id: str) -> "SystemState":
        """Return new state with file removed (immutable update)."""
        file_obj = self.files.get(file_id)
        if not file_obj:
            return self
        
        new_files = {k: v for k, v in self.files.items() if k != file_id}
        
        # Update blueprint's file_ids set
        blueprint = self.blueprints.get(file_obj.blueprint_id)
        if blueprint:
            new_file_ids = blueprint.file_ids - {file_id}
            new_blueprint = Blueprint(
                blueprint_id=blueprint.blueprint_id,
                name=blueprint.name,
                description=blueprint.description,
                owner=blueprint.owner,
                file_ids=new_file_ids
            )
            new_blueprints = {**self.blueprints, new_blueprint.blueprint_id: new_blueprint}
        else:
            new_blueprints = self.blueprints
        
        return SystemState(blueprints=new_blueprints, files=new_files)


@dataclass(frozen=True)
class Result:
    """
    Typed result matching Oracle's error kind mapping.
    Enables Shell to map Core failures to HTTP status codes.
    """
    success: bool
    value: Optional[Any] = None
    error_kind: Optional[str] = None  # NotFound, Unauthorized, Conflict, Precondition
    error_message: Optional[str] = None
    
    @classmethod
    def ok(cls, value: Any) -> "Result":
        """Create successful result."""
        return cls(success=True, value=value)
    
    @classmethod
    def failure(cls, kind: str, message: str) -> "Result":
        """
        Create failure result with error kind.
        
        Error kinds:
        - NotFound: Resource (blueprint/file) not found in state
        - Unauthorized: Owner mismatch (403)
        - Conflict: Uniqueness violation (409)
        - Precondition: Input validation failure (400)
        """
        return cls(success=False, error_kind=kind, error_message=message)
