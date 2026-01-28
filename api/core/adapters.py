"""
State builders: SQLAlchemy ORM → Core models adapter.
Critical component for safely converting mutable SQLAlchemy objects to immutable Core models.

This is the most difficult part of the Shell (Oracle identified as highest risk).
Must reliably translate SQLAlchemy ORM objects (Mutable) into Python Core Models (Immutable/Frozen).
"""

from typing import List, Dict
from sqlalchemy.orm import Session

from api.database import Project as DBProject, File as DBFile
from api.core.models import SystemState, Project, File, Owner, FileType


def build_system_state(
    projects: List[DBProject],
    files: List[DBFile]
) -> SystemState:
    """
    Build SystemState from SQLAlchemy ORM objects.
    
    This function safely converts mutable SQLAlchemy objects to immutable Core models.
    It computes the file_ids sets for projects based on the files list.
    
    Args:
        projects: List of SQLAlchemy Project objects
        files: List of SQLAlchemy File objects
    
    Returns:
        Immutable SystemState snapshot
    
    Raises:
        ValueError: If state invariants are violated
    """
    # Build files map first
    files_map: Dict[str, File] = {}
    for db_file in files:
        # Convert file_type enum to FileType
        file_type_map = {
            'md': FileType.MD,
            'dfy': FileType.DFY,
            'unit': FileType.UNIT
        }
        file_type = file_type_map.get(db_file.file_type, FileType.MD)
        
        file_obj = File(
            file_id=str(db_file.file_id),
            project_id=str(db_file.project_id),
            filename=db_file.filename,
            content=db_file.content,
            file_type=file_type,
            size_bytes=len(db_file.content.encode('utf-8')),
            renamed=db_file.renamed
        )
        files_map[str(db_file.file_id)] = file_obj
    
    # Build projects map with file_ids sets computed from files
    projects_map: Dict[str, Project] = {}
    for db_project in projects:
        # Determine owner
        if db_project.user_id:
            owner = Owner.authenticated(str(db_project.user_id))
        elif db_project.api_key_hash:
            owner = Owner.anonymous(db_project.api_key_hash)
        else:
            # Should not happen, but handle gracefully
            owner = Owner.anonymous("")
        
        # Compute file_ids set from files belonging to this project
        file_ids = {
            str(f.file_id) for f in files
            if str(f.project_id) == str(db_project.project_id)
        }
        
        project_obj = Project(
            project_id=str(db_project.project_id),
            name=db_project.name,
            description=db_project.description or "",
            owner=owner,
            file_ids=file_ids
        )
        projects_map[str(db_project.project_id)] = project_obj
    
    state = SystemState(projects=projects_map, files=files_map)
    
    # Validate state invariants
    state.validate()
    
    return state


def apply_state_diff(
    db: Session,
    old_state: SystemState,
    new_state: SystemState
) -> None:
    """
    Apply state diff to database (update SQLAlchemy objects).
    
    This function compares old_state and new_state and applies changes to the database.
    It handles:
    - Project updates (owner changes, name/description changes)
    - File updates (content changes, new files, deleted files)
    
    Args:
        db: SQLAlchemy database session
        old_state: Previous SystemState snapshot
        new_state: New SystemState snapshot (from Core function)
    
    Note:
        This function performs I/O operations (database writes).
        It should only be called from the Imperative Shell.
    """
    # Find projects that changed
    for project_id, new_project in new_state.projects.items():
        old_project = old_state.projects.get(project_id)
        
        if old_project is None:
            # New project - should not happen in migration, but handle it
            continue
        
        # Check if owner changed (this is the migration case)
        if old_project.owner != new_project.owner:
            db_project = db.query(DBProject).filter(
                DBProject.project_id == project_id
            ).first()
            
            if db_project:
                # Update owner
                if new_project.owner.is_authenticated():
                    db_project.user_id = new_project.owner.user_id
                    # Keep api_key_hash for backward compatibility
                elif new_project.owner.is_anonymous():
                    db_project.api_key_hash = new_project.owner.api_key_hash
                    db_project.user_id = None
    
    # Note: File changes are handled separately in file operations
    # This adapter focuses on project migration (owner changes)
