"""
TKA (Trusted Kernel Architecture) Initialization API Routes

Endpoints for bootstrapping new InspecThor projects.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from api.auth import get_current_user
from api.files import get_api_key_from_header
from api.services.tka_initializer import TKAInitializer, TKAConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tka", tags=["tka"])


# Request/Response Models
class InitializeProjectRequest(BaseModel):
    """Request to initialize TKA for a project"""
    project_name: str = Field(..., description="Project name")
    project_description: str = Field(..., description="Project description")
    repo_path: str = Field(..., description="Repository path")
    enable_git_hooks: bool = Field(True, description="Install Git hooks")
    enable_iron_grip: bool = Field(False, description="Enable Iron Grip protection")
    github_owner: Optional[str] = Field(None, description="GitHub owner")
    github_repo: Optional[str] = Field(None, description="GitHub repo")
    initial_components: Optional[List[str]] = Field(
        default=None,
        description="Initial components to create"
    )


class InitializeProjectResponse(BaseModel):
    """Response from project initialization"""
    success: bool
    project_name: str
    brain_path: str
    components_initialized: int
    blueprints_created: int
    proof_ledger_initialized: bool
    git_hooks_installed: bool
    iron_grip_enabled: bool
    errors: List[str]
    warnings: List[str]
    message: str


@router.post("/initialize", response_model=InitializeProjectResponse)
async def initialize_project(
    request: InitializeProjectRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Initialize Trusted Kernel Architecture for a new project

    This creates:
    - .inspecthor/ Brain directory structure
    - Component registry
    - Cryptographic proof ledger with Ed25519 keys
    - Initial blueprints
    - Project configuration
    - Git hooks (optional)
    - Iron Grip protection (optional)

    This is the entry point for starting a new InspecThor project.
    """
    try:
        logger.info(
            f"TKA initialization requested for '{request.project_name}' "
            f"by user {current_user.get('email', 'unknown')}"
        )

        # Create TKA config
        config = TKAConfig(
            project_name=request.project_name,
            project_description=request.project_description,
            repo_path=request.repo_path,
            enable_git_hooks=request.enable_git_hooks,
            enable_iron_grip=request.enable_iron_grip,
            github_owner=request.github_owner,
            github_repo=request.github_repo,
            initial_components=request.initial_components or []
        )

        # Initialize TKA
        initializer = TKAInitializer()
        result = initializer.initialize_project(config)

        # Build response message
        if result.success:
            message = (
                f"✅ TKA initialized successfully for '{request.project_name}'. "
                f"{result.components_initialized} component(s), "
                f"{result.blueprints_created} blueprint(s) created."
            )
        else:
            message = f"❌ TKA initialization failed: {', '.join(result.errors)}"

        logger.info(f"TKA initialization result: {message}")

        return InitializeProjectResponse(
            success=result.success,
            project_name=result.project_name,
            brain_path=result.brain_path,
            components_initialized=result.components_initialized,
            blueprints_created=result.blueprints_created,
            proof_ledger_initialized=result.proof_ledger_initialized,
            git_hooks_installed=result.git_hooks_installed,
            iron_grip_enabled=result.iron_grip_enabled,
            errors=result.errors,
            warnings=result.warnings,
            message=message
        )

    except Exception as e:
        logger.error(f"TKA initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def tka_health(
    api_key: str = Depends(get_api_key_from_header)
):
    """
    Check TKA service health
    """
    return {
        "status": "ok",
        "service": "TKA Initializer",
        "message": "Ready to bootstrap InspecThor projects"
    }
