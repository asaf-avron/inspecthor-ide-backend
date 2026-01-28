"""
State builders: SQLAlchemy ORM → Core models adapter.
Critical component for safely converting mutable SQLAlchemy objects to immutable Core models.

This is the most difficult part of the Shell (Oracle identified as highest risk).
Must reliably translate SQLAlchemy ORM objects (Mutable) into Python Core Models (Immutable/Frozen).
"""

from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import uuid as uuid_module

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
        file_type = file_type_map.get(str(db_file.file_type), FileType.MD)  # type: ignore[arg-type]
        
        file_obj = File(
            file_id=str(db_file.file_id),
            project_id=str(db_file.project_id),
            filename=str(db_file.filename),  # type: ignore[arg-type]
            content=str(db_file.content),  # type: ignore[arg-type]
            file_type=file_type,
            size_bytes=len(db_file.content.encode('utf-8')),
            renamed=bool(db_file.renamed)  # type: ignore[arg-type]
        )
        files_map[str(db_file.file_id)] = file_obj
    
    # Build projects map with file_ids sets computed from files
    projects_map: Dict[str, Project] = {}
    for db_project in projects:
        # Determine owner
        if db_project.user_id:
            owner = Owner.authenticated(str(db_project.user_id))
        elif db_project.api_key_hash:
            owner = Owner.anonymous(str(db_project.api_key_hash))  # type: ignore[arg-type]
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
            name=str(db_project.name),  # type: ignore[arg-type]
            description=str(db_project.description) if db_project.description else "",  # type: ignore[arg-type]
            owner=owner,
            file_ids=file_ids
        )
        projects_map[str(db_project.project_id)] = project_obj
    
    state = SystemState(projects=projects_map, files=files_map)
    
    # Validate state invariants
    state.validate()
    
    # Scope Contract: Ensure every file has a corresponding project
    for file_id, file_obj in files_map.items():
        if file_obj.project_id not in projects_map:
            raise ValueError(
                f"Scope Contract violation: File {file_id} references project {file_obj.project_id} "
                f"that is not in the projects list"
            )
    
    return state


def build_scoped_state(
    project_id: Optional[str] = None,
    owner_filter: Optional[Any] = None,
    db: Optional[Session] = None
) -> SystemState:
    """
    Build scoped SystemState for a specific operation (Oracle's Scope Contract).
    
    When loading state for a specific operation (e.g., save_file(project_id=P)),
    ensures Project P and ALL its files are loaded. This prevents uniqueness check
    failures when only a partial state is loaded.
    
    Args:
        project_id: Specific project ID to load (if None, loads all)
        owner_filter: SQLAlchemy filter for ownership (if None, loads all)
        db: Database session
    
    Returns:
        SystemState snapshot containing the working set
    
    Raises:
        ValueError: If scope contract is violated
    """
    if db is None:
        raise ValueError("Database session required for build_scoped_state")
    
    # Load projects
    query_projects = db.query(DBProject)
    if project_id:
        # Convert string to UUID if needed
        try:
            project_uuid = uuid_module.UUID(project_id) if isinstance(project_id, str) else project_id
            query_projects = query_projects.filter(DBProject.project_id == project_uuid)
        except ValueError:
            # Invalid UUID format
            return SystemState(projects={}, files={})
    if owner_filter is not None:
        query_projects = query_projects.filter(owner_filter)
    projects = query_projects.all()
    
    if not projects:
        # Return empty state if no projects found
        return SystemState(projects={}, files={})
    
    # Load ALL files for the projects in scope
    project_uuids = [p.project_id for p in projects]  # Keep as UUID objects for DB query
    files = db.query(DBFile).filter(DBFile.project_id.in_(project_uuids)).all()
    
    return build_system_state(projects, files)


def apply_state_diff(
    db: Session,
    old_state: SystemState,
    new_state: SystemState
) -> None:
    """
    Generic Diff Engine (Oracle's pattern).
    
    Applies state diff to database with strict ordering to avoid FK constraint violations.
    Order of operations is critical:
    1. DELETE Files (children first)
    2. DELETE Projects (parents second)
    3. CREATE Projects (parents first)
    4. CREATE Files (children second)
    5. UPDATE (any order)
    
    Args:
        db: SQLAlchemy database session
        old_state: Previous SystemState snapshot
        new_state: New SystemState snapshot (from Core function)
    
    Note:
        This function performs I/O operations (database writes).
        It should only be called from the Imperative Shell.
    """
    # --- 1. DELETIONS (Children First) ---
    # Files first
    deleted_files = set(old_state.files.keys()) - set(new_state.files.keys())
    for file_id in deleted_files:
        file_uuid = uuid_module.UUID(file_id) if isinstance(file_id, str) else file_id
        db.query(DBFile).filter(DBFile.file_id == file_uuid).delete()
    
    # Projects second (parents)
    deleted_projects = set(old_state.projects.keys()) - set(new_state.projects.keys())
    for project_id in deleted_projects:
        project_uuid = uuid_module.UUID(project_id) if isinstance(project_id, str) else project_id
        db.query(DBProject).filter(DBProject.project_id == project_uuid).delete()
    
    # --- 2. CREATES & UPDATES ---
    # Projects first (parents)
    for project_id, new_proj in new_state.projects.items():
        old_proj = old_state.projects.get(project_id)
        
        if old_proj is None:
            # CREATE: New project
            project_uuid = uuid_module.UUID(project_id) if isinstance(project_id, str) else project_id
            db_proj = DBProject(
                project_id=project_uuid,
                name=new_proj.name,
                description=new_proj.description or None,
                user_id=uuid_module.UUID(new_proj.owner.user_id) if new_proj.owner.is_authenticated() else None,
                api_key_hash=new_proj.owner.api_key_hash if new_proj.owner.is_anonymous() else None
            )
            db.add(db_proj)
        elif new_proj != old_proj:
            # UPDATE: Project changed
            project_uuid = uuid_module.UUID(project_id) if isinstance(project_id, str) else project_id
            db_proj = db.query(DBProject).filter(DBProject.project_id == project_uuid).first()  # type: ignore[assignment]
            if db_proj:
                # Update fields
                db_proj.name = new_proj.name  # type: ignore[assignment]
                db_proj.description = new_proj.description or None  # type: ignore[assignment]
                
                # Handle owner changes
                if new_proj.owner.is_authenticated():
                    db_proj.user_id = uuid_module.UUID(new_proj.owner.user_id)  # type: ignore[assignment]
                    # Keep api_key_hash for backward compatibility
                elif new_proj.owner.is_anonymous():
                    db_proj.api_key_hash = new_proj.owner.api_key_hash  # type: ignore[assignment]
                    db_proj.user_id = None  # type: ignore[assignment]
    
    # Files second (children)
    for file_id, new_file in new_state.files.items():
        old_file = old_state.files.get(file_id)
        file_uuid = uuid_module.UUID(file_id) if isinstance(file_id, str) else file_id
        project_uuid = uuid_module.UUID(new_file.project_id) if isinstance(new_file.project_id, str) else new_file.project_id
        
        if old_file is None:
            # CREATE: New file
            db_file = DBFile(
                file_id=file_uuid,
                project_id=project_uuid,
                filename=new_file.filename,
                content=new_file.content,
                file_type=new_file.file_type.value,
                renamed=new_file.renamed
            )
            db.add(db_file)
        elif new_file != old_file:
            # UPDATE: File changed
            db_file = db.query(DBFile).filter(DBFile.file_id == file_uuid).first()  # type: ignore[assignment]
            if db_file:  # type: ignore[assignment]
                db_file.content = new_file.content  # type: ignore[assignment]
                db_file.filename = new_file.filename  # type: ignore[assignment]
                db_file.file_type = new_file.file_type.value  # type: ignore[assignment]
                db_file.renamed = new_file.renamed  # type: ignore[assignment]
