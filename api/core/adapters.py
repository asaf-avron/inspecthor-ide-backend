"""
State builders: SQLAlchemy ORM → Core models adapter.
Critical component for safely converting mutable SQLAlchemy objects to immutable Core models.

This is the most difficult part of the Shell (Oracle identified as highest risk).
Must reliably translate SQLAlchemy ORM objects (Mutable) into Python Core Models (Immutable/Frozen).
"""

from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import uuid as uuid_module

from api.database import Blueprint as DBBlueprint, File as DBFile
from api.core.models import SystemState, Blueprint, File, Owner, FileType


def build_system_state(
    blueprints: List[DBBlueprint],
    files: List[DBFile]
) -> SystemState:
    """
    Build SystemState from SQLAlchemy ORM objects.
    
    This function safely converts mutable SQLAlchemy objects to immutable Core models.
    It computes the file_ids sets for blueprints based on the files list.
    
    Args:
        blueprints: List of SQLAlchemy Blueprint objects
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
            blueprint_id=str(db_file.blueprint_id),
            filename=str(db_file.filename),  # type: ignore[arg-type]
            content=str(db_file.content),  # type: ignore[arg-type]
            file_type=file_type,
            size_bytes=len(db_file.content.encode('utf-8')),
            renamed=bool(db_file.renamed)  # type: ignore[arg-type]
        )
        files_map[str(db_file.file_id)] = file_obj
    
    # Build blueprints map with file_ids sets computed from files
    blueprints_map: Dict[str, Blueprint] = {}
    for db_blueprint in blueprints:
        # Determine owner
        if db_blueprint.user_id:
            owner = Owner.authenticated(str(db_blueprint.user_id))
        elif db_blueprint.api_key_hash:
            owner = Owner.anonymous(str(db_blueprint.api_key_hash))  # type: ignore[arg-type]
        else:
            # Should not happen, but handle gracefully
            owner = Owner.anonymous("")
        
        # Compute file_ids set from files belonging to this blueprint
        file_ids = {
            str(f.file_id) for f in files
            if str(f.blueprint_id) == str(db_blueprint.blueprint_id)
        }
        
        blueprint_obj = Blueprint(
            blueprint_id=str(db_blueprint.blueprint_id),
            name=str(db_blueprint.name),  # type: ignore[arg-type]
            description=str(db_blueprint.description) if db_blueprint.description else "",  # type: ignore[arg-type]
            owner=owner,
            file_ids=file_ids
        )
        blueprints_map[str(db_blueprint.blueprint_id)] = blueprint_obj
    
    state = SystemState(blueprints=blueprints_map, files=files_map)
    
    # Validate state invariants
    state.validate()
    
    # Scope Contract: Ensure every file has a corresponding blueprint
    for file_id, file_obj in files_map.items():
        if file_obj.blueprint_id not in blueprints_map:
            raise ValueError(
                f"Scope Contract violation: File {file_id} references blueprint {file_obj.blueprint_id} "
                f"that is not in the blueprints list"
            )
    
    return state


def build_scoped_state(
    blueprint_id: Optional[str] = None,
    owner_filter: Optional[Any] = None,
    db: Optional[Session] = None
) -> SystemState:
    """
    Build scoped SystemState for a specific operation (Oracle's Scope Contract).
    
    When loading state for a specific operation (e.g., save_file(blueprint_id=P)),
    ensures Blueprint P and ALL its files are loaded. This prevents uniqueness check
    failures when only a partial state is loaded.
    
    Args:
        blueprint_id: Specific blueprint ID to load (if None, loads all)
        owner_filter: SQLAlchemy filter for ownership (if None, loads all)
        db: Database session
    
    Returns:
        SystemState snapshot containing the working set
    
    Raises:
        ValueError: If scope contract is violated
    """
    if db is None:
        raise ValueError("Database session required for build_scoped_state")
    
    # Load blueprints
    query_blueprints = db.query(DBBlueprint)
    if blueprint_id:
        # Convert string to UUID if needed
        try:
            blueprint_uuid = uuid_module.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
            query_blueprints = query_blueprints.filter(DBBlueprint.blueprint_id == blueprint_uuid)
        except ValueError:
            # Invalid UUID format
            return SystemState(blueprints={}, files={})
    if owner_filter is not None:
        query_blueprints = query_blueprints.filter(owner_filter)
    blueprints = query_blueprints.all()
    
    if not blueprints:
        # Return empty state if no blueprints found
        return SystemState(blueprints={}, files={})
    
    # Load ALL files for the blueprints in scope
    blueprint_uuids = [p.blueprint_id for p in blueprints]  # Keep as UUID objects for DB query
    files = db.query(DBFile).filter(DBFile.blueprint_id.in_(blueprint_uuids)).all()
    
    return build_system_state(blueprints, files)


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
    print(f"DEBUG: apply_state_diff called. New files keys: {list(new_state.files.keys())}")
    # --- 1. DELETIONS (Children First) ---
    # Files first
    deleted_files = set(old_state.files.keys()) - set(new_state.files.keys())
    for file_id in deleted_files:
        file_uuid = uuid_module.UUID(file_id) if isinstance(file_id, str) else file_id
        db.query(DBFile).filter(DBFile.file_id == file_uuid).delete()
    
    # Blueprints second (parents)
    deleted_blueprints = set(old_state.blueprints.keys()) - set(new_state.blueprints.keys())
    for blueprint_id in deleted_blueprints:
        blueprint_uuid = uuid_module.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
        db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_uuid).delete()
    
    # --- 2. CREATES & UPDATES ---
    # Blueprints first (parents)
    for blueprint_id, new_proj in new_state.blueprints.items():
        old_proj = old_state.blueprints.get(blueprint_id)
        
        if old_proj is None:
            # CREATE: New blueprint
            blueprint_uuid = uuid_module.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
            db_proj = DBBlueprint(
                blueprint_id=blueprint_uuid,
                name=new_proj.name,
                description=new_proj.description or None,
                user_id=uuid_module.UUID(new_proj.owner.user_id) if new_proj.owner.is_authenticated() else None,
                api_key_hash=new_proj.owner.api_key_hash if new_proj.owner.is_anonymous() else None
            )
            db.add(db_proj)
        elif new_proj != old_proj:
            # UPDATE: Blueprint changed
            blueprint_uuid = uuid_module.UUID(blueprint_id) if isinstance(blueprint_id, str) else blueprint_id
            db_proj = db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_uuid).first()  # type: ignore[assignment]
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
        blueprint_uuid = uuid_module.UUID(new_file.blueprint_id) if isinstance(new_file.blueprint_id, str) else new_file.blueprint_id
        
        if old_file is None:
            print(f"DEBUG: Creating file {file_id} for blueprint {blueprint_uuid}")
            # CREATE: New file
            db_file = DBFile(
                file_id=file_uuid,
                blueprint_id=blueprint_uuid,
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
