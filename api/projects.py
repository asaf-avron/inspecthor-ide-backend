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

from api.database import get_db, hash_api_key, Project as DBProject, File as DBFile
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


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Create a new project and bootstrap initial README.md file.
    Returns project details with redirect_url for frontend navigation.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    api_key_hash_value = hash_api_key(api_key)
    
    logger.info(f"Creating project: name='{request.name}', description length={len(request.description) if request.description else 0}")
    
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
    
    # Check for existing project (case-insensitive)
    existing = db.query(DBProject).filter(
        DBProject.api_key_hash == api_key_hash_value,
        func.lower(DBProject.name) == name_trimmed.lower()
    ).first()
    
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
    db: Session = Depends(get_db)
):
    """
    List all projects owned by the requesting API key with pagination and sorting.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Base query: only projects owned by this API key
    query = db.query(DBProject).filter(DBProject.api_key_hash == api_key_hash_value)
    
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
    db: Session = Depends(get_db)
):
    """
    Get project metadata AND file tree in one RTT (Round Trip Time).
    Optimized to prevent waterfall loading in frontend.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Load project with ownership check
    project = db.query(DBProject).filter(
        DBProject.project_id == project_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
    db: Session = Depends(get_db)
):
    """
    Get single project details.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    project = db.query(DBProject).filter(
        DBProject.project_id == project_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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
    db: Session = Depends(get_db)
):
    """
    Update project name and/or description (partial update).
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Load project with ownership check
    project = db.query(DBProject).filter(
        DBProject.project_id == project_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate at least one field is provided
    if request.name is None and request.description is None:
        raise HTTPException(status_code=400, detail="At least one field must be provided")
    
    # If name is provided, check uniqueness
    if request.name is not None:
        if len(request.name) < 1 or len(request.name) > 255:
            raise HTTPException(status_code=400, detail="Invalid name length (1-255 characters)")
        
        if request.name != project.name:
            existing = db.query(DBProject).filter(
                DBProject.api_key_hash == api_key_hash_value,
                func.lower(DBProject.name) == request.name.lower(),
                DBProject.project_id != project_id
            ).first()
            
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


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Delete a project and all associated files and unit links atomically (cascade).
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Load project with ownership check
    project = db.query(DBProject).filter(
        DBProject.project_id == project_id,
        DBProject.api_key_hash == api_key_hash_value
    ).first()
    
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
