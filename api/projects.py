"""
Project management endpoints for Guardian Gateway
Handles project CRUD operations with strict API key ownership isolation
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import logging

from api.database import get_db
from api.models import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectListResponse,
    ProjectStructureResponse,
    ProjectDeleteResponse,
)
from api.auth import get_current_user
from api.files import get_api_key_from_header
from api.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])

logger = logging.getLogger(__name__)


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new project.
    Returns project details with redirect_url for frontend navigation.
    """
    service = ProjectService(db, current_user)
    return service.create_project(request, api_key)


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
    service = ProjectService(db, current_user)
    return service.list_projects(limit, offset, sort, order, api_key)


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
    service = ProjectService(db, current_user)
    return service.get_project_structure(project_id, api_key)


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
    service = ProjectService(db, current_user)
    return service.get_project(project_id, api_key)


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
    service = ProjectService(db, current_user)
    return service.update_project(project_id, request, api_key)


@router.delete("/{project_id}", response_model=ProjectDeleteResponse)
async def delete_project(
    project_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a project and all associated files atomically (cascade).
    Automatically migrates anonymous projects to authenticated user before deletion.
    Cascade deletion is handled in Core.
    """
    service = ProjectService(db, current_user)
    return service.delete_project(project_id, api_key)
