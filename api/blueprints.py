"""
Blueprint API endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.auth import get_current_user
from api.services.blueprint_service import BlueprintService
from api.models import (
    BlueprintCreateRequest,
    BlueprintUpdateRequest,
    BlueprintResponse,
    BlueprintListResponse,
    BlueprintStructureResponse,
    BlueprintDeleteResponse,
    BlueprintInitRequest,
    BlueprintInitResponse
)
from api.files import get_api_key_from_header

router = APIRouter(prefix="/api/blueprints", tags=["blueprints"])


def get_blueprint_service(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> BlueprintService:
    """Dependency to get BlueprintService instance"""
    return BlueprintService(db, current_user)


@router.post("", response_model=BlueprintResponse, status_code=201)
async def create_blueprint(
    request: BlueprintCreateRequest,
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    Create a new blueprint.
    """
    return service.create_blueprint(request, api_key)


@router.post("/initialize", response_model=BlueprintInitResponse)
async def initialize_blueprint(
    request: BlueprintInitRequest,
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    Initialize a new blueprint from GitHub.
    """
    return await service.initialize_blueprint(request, api_key)


@router.get("", response_model=BlueprintListResponse)
async def list_blueprints(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("updated_at", regex="^(name|created_at|updated_at)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    List blueprints with pagination and sorting.
    """
    return service.list_blueprints(limit, offset, sort, order, api_key)


@router.get("/{blueprint_id}", response_model=BlueprintResponse)
async def get_blueprint(
    blueprint_id: str,
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    Get blueprint details.
    """
    return service.get_blueprint(blueprint_id, api_key)


@router.get("/{blueprint_id}/structure", response_model=BlueprintStructureResponse)
async def get_blueprint_structure(
    blueprint_id: str,
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    Get blueprint structure (details + file tree).
    """
    return service.get_blueprint_structure(blueprint_id, api_key)


@router.put("/{blueprint_id}", response_model=BlueprintResponse)
async def update_blueprint(
    blueprint_id: str,
    request: BlueprintUpdateRequest,
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    Update blueprint details.
    """
    return service.update_blueprint(blueprint_id, request, api_key)


@router.delete("/{blueprint_id}", response_model=BlueprintDeleteResponse)
async def delete_blueprint(
    blueprint_id: str,
    api_key: str = Depends(get_api_key_from_header),
    service: BlueprintService = Depends(get_blueprint_service)
):
    """
    Delete a blueprint and all its files.
    """
    return service.delete_blueprint(blueprint_id, api_key)
