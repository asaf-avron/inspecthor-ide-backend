"""
Blueprint API endpoints for InspecThor.
Handles blueprint initialization with the Trusted Kernel Architecture.
"""

import logging
import re
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import get_db, Project
from api.files import get_api_key_from_header
from api.auth import get_current_user
from api.services.blueprint_genesis import BlueprintGenesisService, GenesisResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/blueprints", tags=["blueprints"])


class BlueprintInitRequest(BaseModel):
    """Request to initialize a blueprint repository."""
    name: str = Field(..., min_length=1, max_length=100, description="Blueprint name")
    repository_url: str = Field(..., description="GitHub repository URL")
    installation_id: int = Field(..., description="GitHub App installation ID")
    domain: str = Field(
        default="custom",
        description="Domain preset: banking, healthcare, authentication, custom"
    )
    force: bool = Field(
        default=False,
        description="Force initialization even if repo is not empty"
    )


class BlueprintInitResponse(BaseModel):
    """Response from blueprint initialization."""
    blueprint_id: str
    name: str
    repository_url: str
    commit_sha: str
    commit_url: str
    files_created: list[str]
    default_branch: str
    next_steps: list[str]


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Parse GitHub URL to extract owner and repo.
    
    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    
    Returns:
        Tuple of (owner, repo)
    
    Raises:
        ValueError: If URL format is invalid
    """
    # HTTPS format
    https_match = re.match(r'https?://github\.com/([^/]+)/([^/\.]+)(?:\.git)?/?$', url)
    if https_match:
        return https_match.group(1), https_match.group(2)
    
    # SSH format
    ssh_match = re.match(r'git@github\.com:([^/]+)/([^/\.]+)(?:\.git)?$', url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)
    
    raise ValueError(f"Invalid GitHub repository URL: {url}")


@router.post("/initialize", response_model=BlueprintInitResponse, status_code=status.HTTP_201_CREATED)
async def initialize_blueprint(
    request: BlueprintInitRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Initialize a GitHub repository with the Trusted Kernel Architecture.
    
    The Genesis Event:
    1. Verifies repository is empty (or only contains README/LICENSE)
    2. Pushes template files (blueprint.yaml, kernel/, shell/, etc.)
    3. Creates database record for the blueprint
    4. Returns commit information and next steps
    
    The pushed files include a GitHub Actions workflow that enforces
    verification on all pull requests.
    """
    # Parse repository URL
    try:
        owner, repo = parse_github_url(request.repository_url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Initialize repository
    genesis_service = BlueprintGenesisService()
    
    try:
        result = await genesis_service.initialize_repository(
            installation_id=request.installation_id,
            owner=owner,
            repo=repo,
            blueprint_name=request.name,
            domain=request.domain,
            force=request.force
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Genesis failed for {owner}/{repo}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize repository: {str(e)}"
        )
    
    # Create database record (using existing Project model for now)
    # TODO: Phase 1 will rename Project to Blueprint
    blueprint_id = uuid4()
    
    project = Project(
        project_id=blueprint_id,
        name=request.name,
        description=f"Blueprint initialized from {request.repository_url}",
        user_id=current_user.user_id if current_user else None,
    )
    
    if request.force and current_user:
        # If force is True, delete any existing project with the same name for this user
        existing_project = db.query(Project).filter(
            Project.user_id == current_user.user_id,
            Project.name == request.name
        ).first()
        if existing_project:
            logger.warning(f"Force init: removing existing project {existing_project.project_id}")
            db.delete(existing_project)
            db.commit()

    db.add(project)
    db.commit()
    
    logger.info(f"Blueprint created: {blueprint_id} for {owner}/{repo}")
    
    return BlueprintInitResponse(
        blueprint_id=str(blueprint_id),
        name=request.name,
        repository_url=request.repository_url,
        commit_sha=result.commit_sha,
        commit_url=result.commit_url,
        files_created=result.files_created,
        default_branch=result.default_branch,
        next_steps=[
            f"View your repository: https://github.com/{owner}/{repo}",
            "Add a claim file in the claims/ directory",
            "Write your specification following the claim format",
            "Run verification to generate Dafny contracts",
            "Push verified code back to GitHub"
        ]
    )
