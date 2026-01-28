"""
Project management endpoints for Guardian Gateway
Handles project CRUD operations with strict API key ownership isolation
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime
import logging
import icontract

from api.database import get_db, hash_api_key, Project as DBProject, File as DBFile, User
from api.models import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectListRequest,
    ProjectListResponse,
    ProjectStructureResponse,
    ProjectDeleteResponse,
    FileMetadata,
)
from api.auth import get_current_user
from api.core import adapters, migration

router = APIRouter(prefix="/api/projects", tags=["projects"])

logger = logging.getLogger(__name__)


def get_api_key_from_header(
    x_api_key: Optional[str] = Header(None),
    request: Request = None
) -> str:
    """
    Extract API key or generate anonymous session key.
    For anonymous users (local-first), creates a session key based on IP.
    For authenticated users, uses provided API key.
    """
    if x_api_key:
        return x_api_key
    
    # Anonymous user - generate session key from IP
    # This ensures each browser session gets isolated projects
    if request and request.client:
        client_ip = request.client.host
        # Use IP as anonymous identifier (could be enhanced with session cookies later)
        return f"anon_{client_ip}"
    
    # Fallback for truly anonymous (shouldn't happen)
    return "anon_default"


def get_project_owner_id(
    user: Optional[User] = None,
    api_key: Optional[str] = None,
    db: Optional[Session] = None
) -> tuple[Optional[str], Optional[str]]:
    """
    Get project owner identifier (user_id or api_key_hash).
    Returns (user_id, api_key_hash) tuple - one will be None.
    Prioritizes authenticated user over API key.
    """
    if user:
        return (str(user.user_id), None)
    
    if api_key:
        api_key_hash_value = hash_api_key(api_key)
        return (None, api_key_hash_value)
    
    return (None, None)


@icontract.require(
    lambda user, api_key_hash_value, db:
        user is not None and
        api_key_hash_value is not None and
        len(api_key_hash_value) > 0 and
        db is not None,
    "Preconditions: user must be authenticated, api_key_hash must be valid, db session must exist"
)
@icontract.ensure(
    lambda result, user, api_key_hash_value, db, OLD:
        result >= 0,
    "Postconditions: return value >= 0 (number of migrated projects)"
)
def migrate_anonymous_projects_to_user(
    user: User,
    api_key_hash_value: str,
    db: Session
) -> int:
    """
    Migrate anonymous projects (created with api_key_hash) to authenticated user.
    This happens when a user logs in and has projects created before authentication.
    Returns the number of projects migrated.
    
    Refactored to use Functional Core / Imperative Shell architecture:
    - Shell (I/O): Fetch state, apply diff, commit
    - Core (Logic): Pure migration function matching Dafny spec
    
    See: api/verification/project_migration.dfy :: MigrateAnonymousProjects
    See: api/core/migration.py :: migrate_anonymous_projects
    """
    # 1. I/O: Fetch snapshot (all projects and files for full state)
    projects = db.query(DBProject).all()
    files = db.query(DBFile).all()
    
    # 2. ADAPTER: Build SystemState from SQLAlchemy objects
    old_state = adapters.build_system_state(projects, files)
    
    # Count projects that will be migrated (before migration)
    projects_to_migrate = [
        p for p in projects
        if p.api_key_hash == api_key_hash_value and p.user_id is None
    ]
    migrated_count = len(projects_to_migrate)
    
    if migrated_count == 0:
        return 0
    
    # 3. CORE: Call pure logic (matches Dafny MigrateAnonymousProjects)
    new_state = migration.migrate_anonymous_projects(
        old_state,
        str(user.user_id),
        api_key_hash_value
    )
    
    # 4. ADAPTER: Apply state diff back to database
    adapters.apply_state_diff(db, old_state, new_state)
    
    # 5. I/O: Commit changes
    db.commit()
    
    logger.info(f"Migrated {migrated_count} anonymous projects to user {user.user_id}")
    return migrated_count


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new project and bootstrap initial README.md file.
    Returns project details with redirect_url for frontend navigation.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    user_id, api_key_hash_value = get_project_owner_id(current_user, api_key, db)
    
    logger.info(f"Creating project: name='{request.name}', user_id={user_id}, api_key_hash={api_key_hash_value[:20] if api_key_hash_value else None}")
    
    # Validate name - Pydantic should handle None, but check for empty string
    if not request.name:
        logger.warning("No project name provided")
        raise HTTPException(status_code=400, detail="Project name is required")
    
    name_trimmed = request.name.strip()
    if len(name_trimmed) == 0:
        logger.warning("Empty project name provided")
        raise HTTPException(status_code=400, detail="Project name cannot be empty")
    
    if len(name_trimmed) > 255:
        logger.warning(f"Project name too long: {len(name_trimmed)} characters")
        raise HTTPException(status_code=400, detail="Invalid name length (1-255 characters)")
    
    # Check for existing project (case-insensitive) - check by user_id or api_key_hash
    query = db.query(DBProject).filter(func.lower(DBProject.name) == name_trimmed.lower())
    if user_id:
        query = query.filter(DBProject.user_id == user_id)
    else:
        query = query.filter(DBProject.api_key_hash == api_key_hash_value)
    
    existing = query.first()
    
    if existing:
        logger.warning(f"Duplicate project name: '{name_trimmed}'")
        raise HTTPException(status_code=400, detail="Project name already exists")
    
    # Validate description length
    if request.description and len(request.description) > 1000:
        logger.warning(f"Description too long: {len(request.description)} characters")
        raise HTTPException(status_code=400, detail="Description too long (max 1000 characters)")
    
    # Create project (use trimmed name) - empty, no auto-generated files
    project = DBProject(
        name=name_trimmed,
        description=request.description,
        user_id=user_id,
        api_key_hash=api_key_hash_value
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return ProjectResponse(
        project_id=str(project.project_id),
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        file_count=0,
        redirect_url=f"/app/{project.project_id}"
    )


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort: str = Query("updated_at", pattern="^(created_at|updated_at|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all projects owned by the authenticated user or API key with pagination and sorting.
    Automatically migrates anonymous projects to authenticated user on first access.
    """
    user_id, api_key_hash_value = get_project_owner_id(current_user, api_key, db)
    
    # Migrate anonymous projects to authenticated user if logged in
    if current_user and api_key_hash_value:
        migrate_anonymous_projects_to_user(current_user, api_key_hash_value, db)
    
    # Base query: filter by user_id (if authenticated) or api_key_hash (if anonymous)
    query = db.query(DBProject)
    if user_id:
        query = query.filter(DBProject.user_id == user_id)
    else:
        query = query.filter(DBProject.api_key_hash == api_key_hash_value)
    
    # Count total before pagination
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(DBProject, sort)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    projects = query.limit(limit).offset(offset).all()
    
    # Get file count for each project (optimized with join)
    project_responses = []
    for project in projects:
        file_count = db.query(DBFile).filter(DBFile.project_id == project.project_id).count()
        project_responses.append(ProjectResponse(
            project_id=str(project.project_id),
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            file_count=file_count
        ))
    
    return ProjectListResponse(
        projects=project_responses,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{project_id}/structure", response_model=ProjectStructureResponse)
async def get_project_structure(
    project_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get project metadata AND file tree in one RTT (Round Trip Time).
    Optimized to prevent waterfall loading in frontend.
    Automatically migrates anonymous projects to authenticated user on access.
    """
    user_id, api_key_hash_value = get_project_owner_id(current_user, api_key, db)
    
    # Migrate anonymous projects to authenticated user if logged in
    if current_user and api_key_hash_value:
        migrate_anonymous_projects_to_user(current_user, api_key_hash_value, db)
    
    # Load project with ownership check
    query = db.query(DBProject).filter(DBProject.project_id == project_id)
    if user_id:
        # Check both user_id and api_key_hash (for projects being migrated)
        from sqlalchemy import or_
        query = query.filter(
            or_(
                DBProject.user_id == user_id,
                DBProject.api_key_hash == api_key_hash_value
            )
        )
    else:
        query = query.filter(DBProject.api_key_hash == api_key_hash_value)
    
    project = query.first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # If project was found via api_key_hash but user is authenticated, migrate it now
    if current_user and project.user_id is None and project.api_key_hash == api_key_hash_value:
        project.user_id = current_user.user_id
        db.commit()
        db.refresh(project)
    
    # Load all files in one query
    files = db.query(DBFile).filter(
        DBFile.project_id == project_id
    ).order_by(DBFile.filename).all()
    
    # Build response
    return ProjectStructureResponse(
        project=ProjectResponse(
            project_id=str(project.project_id),
            name=project.name,
            description=project.description,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat(),
            file_count=len(files)
        ),
        files=[
            FileMetadata(
                file_id=str(f.file_id),
                filename=f.filename,
                file_type=f.file_type,
                updated_at=f.updated_at.isoformat(),
                size_bytes=len(f.content.encode('utf-8'))
            ) for f in files
        ]
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get single project details.
    Automatically migrates anonymous projects to authenticated user on access.
    """
    user_id, api_key_hash_value = get_project_owner_id(current_user, api_key, db)
    
    # Migrate anonymous projects to authenticated user if logged in
    if current_user and api_key_hash_value:
        migrate_anonymous_projects_to_user(current_user, api_key_hash_value, db)
    
    query = db.query(DBProject).filter(DBProject.project_id == project_id)
    if user_id:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                DBProject.user_id == user_id,
                DBProject.api_key_hash == api_key_hash_value
            )
        )
    else:
        query = query.filter(DBProject.api_key_hash == api_key_hash_value)
    
    project = query.first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # If project was found via api_key_hash but user is authenticated, migrate it now
    if current_user and project.user_id is None and project.api_key_hash == api_key_hash_value:
        project.user_id = current_user.user_id
        db.commit()
        db.refresh(project)
    
    file_count = db.query(DBFile).filter(DBFile.project_id == project_id).count()
    
    return ProjectResponse(
        project_id=str(project.project_id),
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        file_count=file_count
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update project name and/or description (partial update).
    Automatically migrates anonymous projects to authenticated user on access.
    """
    user_id, api_key_hash_value = get_project_owner_id(current_user, api_key, db)
    
    # Migrate anonymous projects to authenticated user if logged in
    if current_user and api_key_hash_value:
        migrate_anonymous_projects_to_user(current_user, api_key_hash_value, db)
    
    # Load project with ownership check
    query = db.query(DBProject).filter(DBProject.project_id == project_id)
    if user_id:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                DBProject.user_id == user_id,
                DBProject.api_key_hash == api_key_hash_value
            )
        )
    else:
        query = query.filter(DBProject.api_key_hash == api_key_hash_value)
    
    project = query.first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # If project was found via api_key_hash but user is authenticated, migrate it now
    if current_user and project.user_id is None and project.api_key_hash == api_key_hash_value:
        project.user_id = current_user.user_id
        db.commit()
        db.refresh(project)
    
    # Validate at least one field is provided
    if request.name is None and request.description is None:
        raise HTTPException(status_code=400, detail="At least one field must be provided")
    
    # If name is provided, check uniqueness
    if request.name is not None:
        if len(request.name) < 1 or len(request.name) > 255:
            raise HTTPException(status_code=400, detail="Invalid name length (1-255 characters)")
        
        if request.name != project.name:
            existing_query = db.query(DBProject).filter(
                func.lower(DBProject.name) == request.name.lower(),
                DBProject.project_id != project_id
            )
            if user_id:
                existing_query = existing_query.filter(DBProject.user_id == user_id)
            else:
                existing_query = existing_query.filter(DBProject.api_key_hash == api_key_hash_value)
            
            existing = existing_query.first()
            
            if existing:
                raise HTTPException(status_code=400, detail="Project name already exists")
            
            project.name = request.name
    
    # Update description if provided
    if request.description is not None:
        if len(request.description) > 1000:
            raise HTTPException(status_code=400, detail="Description too long (max 1000 characters)")
        project.description = request.description
    
    # Update timestamp (SQLAlchemy handles this with onupdate)
    db.commit()
    db.refresh(project)
    
    # Get file count
    file_count = db.query(DBFile).filter(DBFile.project_id == project_id).count()
    
    return ProjectResponse(
        project_id=str(project.project_id),
        name=project.name,
        description=project.description,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat(),
        file_count=file_count
    )


@icontract.require(
    lambda project_id, api_key, db, current_user:
        project_id is not None and
        len(project_id) > 0 and
        db is not None,
    "Preconditions: Valid project_id, db session exists"
)
@icontract.ensure(
    lambda result, project_id, api_key, db, current_user, OLD:
        result is not None and
        result.deleted == True and
        result.project_id == project_id,
    "Postconditions: Project deleted successfully"
)
@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a project and all associated files and unit links atomically (cascade).
    Automatically migrates anonymous projects to authenticated user before deletion.
    """
    user_id, api_key_hash_value = get_project_owner_id(current_user, api_key, db)
    
    # Migrate anonymous projects to authenticated user if logged in
    if current_user and api_key_hash_value:
        migrate_anonymous_projects_to_user(current_user, api_key_hash_value, db)
    
    # Load project with ownership check
    query = db.query(DBProject).filter(DBProject.project_id == project_id)
    if user_id:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                DBProject.user_id == user_id,
                DBProject.api_key_hash == api_key_hash_value
            )
        )
    else:
        query = query.filter(DBProject.api_key_hash == api_key_hash_value)
    
    project = query.first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Count files before deletion (for response)
    file_count = db.query(DBFile).filter(DBFile.project_id == project_id).count()
    
    # Delete project (cascade deletes files and unit_links automatically)
    db.delete(project)
    db.commit()
    
    return ProjectDeleteResponse(
        deleted=True,
        project_id=str(project_id),
        files_deleted=file_count
    )
