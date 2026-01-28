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
    project_id: str
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
class Project:
    """
    Project model matching Dafny Project datatype.
    Immutable dataclass representing a project in the system.
    """
    project_id: str
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
    projects: Dict[str, Project] = field(default_factory=dict)
    files: Dict[str, File] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """
        Validate system state invariants matching Dafny ValidState predicate.
        
        Returns:
            True if state is valid, raises ValueError if invalid
        """
        # 1. Relational Integrity: Every file pointed to by a project exists
        for pid, project in self.projects.items():
            for fid in project.file_ids:
                if fid not in self.files:
                    raise ValueError(f"Project {pid} references file {fid} that doesn't exist")
        
        # 2. Reverse Integrity: Every file points back to its project
        for fid, file_obj in self.files.items():
            if file_obj.project_id not in self.projects:
                raise ValueError(f"File {fid} references project {file_obj.project_id} that doesn't exist")
            
            if fid not in self.projects[file_obj.project_id].file_ids:
                raise ValueError(f"File {fid} not in project {file_obj.project_id}.file_ids")
        
        # 3. Size Integrity: File metadata matches content
        for fid, file_obj in self.files.items():
            expected_size = len(file_obj.content.encode('utf-8'))
            if file_obj.size_bytes != expected_size:
                raise ValueError(f"File {fid} size_bytes ({file_obj.size_bytes}) doesn't match content length ({expected_size})")
        
        return True
    
    def with_project(self, project: Project) -> "SystemState":
        """Return new state with project added/updated (immutable update)."""
        new_projects = {**self.projects, project.project_id: project}
        return SystemState(projects=new_projects, files=self.files)
    
    def with_file(self, file_obj: File) -> "SystemState":
        """Return new state with file added/updated (immutable update)."""
        new_files = {**self.files, file_obj.file_id: file_obj}
        # Update project's file_ids set
        project = self.projects.get(file_obj.project_id)
        if project:
            new_file_ids = project.file_ids | {file_obj.file_id}
            new_project = Project(
                project_id=project.project_id,
                name=project.name,
                description=project.description,
                owner=project.owner,
                file_ids=new_file_ids
            )
            new_projects = {**self.projects, new_project.project_id: new_project}
        else:
            new_projects = self.projects
        
        return SystemState(projects=new_projects, files=new_files)
    
    def without_project(self, project_id: str) -> "SystemState":
        """Return new state with project removed (immutable update)."""
        new_projects = {k: v for k, v in self.projects.items() if k != project_id}
        # Also remove all files belonging to this project
        new_files = {k: v for k, v in self.files.items() if v.project_id != project_id}
        return SystemState(projects=new_projects, files=new_files)
    
    def without_file(self, file_id: str) -> "SystemState":
        """Return new state with file removed (immutable update)."""
        file_obj = self.files.get(file_id)
        if not file_obj:
            return self
        
        new_files = {k: v for k, v in self.files.items() if k != file_id}
        
        # Update project's file_ids set
        project = self.projects.get(file_obj.project_id)
        if project:
            new_file_ids = project.file_ids - {file_id}
            new_project = Project(
                project_id=project.project_id,
                name=project.name,
                description=project.description,
                owner=project.owner,
                file_ids=new_file_ids
            )
            new_projects = {**self.projects, new_project.project_id: new_project}
        else:
            new_projects = self.projects
        
        return SystemState(projects=new_projects, files=new_files)


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
        - NotFound: Resource (project/file) not found in state
        - Unauthorized: Owner mismatch (403)
        - Conflict: Uniqueness violation (409)
        - Precondition: Input validation failure (400)
        """
        return cls(success=False, error_kind=kind, error_message=message)
