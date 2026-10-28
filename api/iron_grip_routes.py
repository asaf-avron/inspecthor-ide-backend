"""
Iron Grip API Routes

Endpoints for managing GitHub branch protection and enforcement
of InspecThor verification requirements.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import logging

from api.auth import get_current_user
from api.files import get_api_key_from_header
from api.services.github_protection_service import GitHubProtectionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/iron-grip", tags=["iron-grip"])


# Request/Response Models
class EnableIronGripRequest(BaseModel):
    """Request to enable Iron Grip for a repository"""
    owner: str = Field(..., description="Repository owner (user or org)")
    repo: str = Field(..., description="Repository name")
    branches: Optional[List[str]] = Field(
        default=None,
        description="Branches to protect (default: main, master)"
    )
    github_token: Optional[str] = Field(
        default=None,
        description="GitHub token (if not using global config)"
    )


class EnableIronGripResponse(BaseModel):
    """Response from enabling Iron Grip"""
    success: bool
    message: str
    protected_branches: List[str]


class DisableIronGripRequest(BaseModel):
    """Request to disable Iron Grip"""
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    branches: Optional[List[str]] = Field(
        default=None,
        description="Branches to unprotect"
    )
    github_token: Optional[str] = Field(default=None)


class DisableIronGripResponse(BaseModel):
    """Response from disabling Iron Grip"""
    success: bool
    message: str


class ProtectionStatusRequest(BaseModel):
    """Request to check protection status"""
    owner: str
    repo: str
    branch: str
    github_token: Optional[str] = None


class ProtectionStatusResponse(BaseModel):
    """Response with protection status"""
    is_protected: bool
    branch: str
    protection_config: Optional[Dict] = None


class ReportCheckRequest(BaseModel):
    """Request to report a status check"""
    owner: str
    repo: str
    commit_sha: str
    check_name: str
    status: str = Field(..., description="queued, in_progress, or completed")
    conclusion: Optional[str] = Field(
        default=None,
        description="success, failure, neutral, cancelled, etc."
    )
    details_url: Optional[str] = None
    output: Optional[Dict] = None
    github_token: Optional[str] = None


class ReportCheckResponse(BaseModel):
    """Response from reporting check"""
    success: bool
    message: str


class ValidateComplianceRequest(BaseModel):
    """Request to validate Iron Grip compliance"""
    owner: str
    repo: str
    commit_sha: str
    github_token: Optional[str] = None


class CheckResult(BaseModel):
    """Individual check result"""
    status: str
    conclusion: Optional[str] = None
    passed: bool = False


class ValidateComplianceResponse(BaseModel):
    """Response from compliance validation"""
    all_passed: bool
    commit: str
    checks: Dict[str, CheckResult]
    missing_checks: List[str]
    failed_checks: List[str]


@router.post("/enable", response_model=EnableIronGripResponse)
async def enable_iron_grip(
    request: EnableIronGripRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Enable Iron Grip protection for a repository

    Applies branch protection rules that enforce:
    - All changes must go through pull requests
    - All InspecThor checks must pass
    - Dafny verification required
    - Drift detection must pass
    - Component architecture validated
    - Call graph compliance checked
    - Proof ledger integrity verified
    """
    try:
        service = GitHubProtectionService(github_token=request.github_token)

        success, message = service.enable_iron_grip(
            owner=request.owner,
            repo=request.repo,
            branches=request.branches
        )

        if not success:
            raise HTTPException(status_code=500, detail=message)

        branches = request.branches or ["main", "master"]

        logger.info(
            f"Iron Grip enabled for {request.owner}/{request.repo} "
            f"by user {current_user.get('email', 'unknown')}"
        )

        return EnableIronGripResponse(
            success=True,
            message=message,
            protected_branches=branches
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enable Iron Grip: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable", response_model=DisableIronGripResponse)
async def disable_iron_grip(
    request: DisableIronGripRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Disable Iron Grip protection for a repository

    Removes branch protection rules. Use with caution!
    """
    try:
        service = GitHubProtectionService(github_token=request.github_token)

        success, message = service.disable_iron_grip(
            owner=request.owner,
            repo=request.repo,
            branches=request.branches
        )

        if not success:
            raise HTTPException(status_code=500, detail=message)

        logger.warning(
            f"Iron Grip disabled for {request.owner}/{request.repo} "
            f"by user {current_user.get('email', 'unknown')}"
        )

        return DisableIronGripResponse(
            success=True,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to disable Iron Grip: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status", response_model=ProtectionStatusResponse)
async def check_protection_status(
    request: ProtectionStatusRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Check if a branch has Iron Grip protection enabled
    """
    try:
        service = GitHubProtectionService(github_token=request.github_token)

        is_protected, config = service.check_protection_status(
            owner=request.owner,
            repo=request.repo,
            branch=request.branch
        )

        return ProtectionStatusResponse(
            is_protected=is_protected,
            branch=request.branch,
            protection_config=config
        )

    except Exception as e:
        logger.error(f"Failed to check protection status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report-check", response_model=ReportCheckResponse)
async def report_status_check(
    request: ReportCheckRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Report a status check result to GitHub

    Used by verification services to report check results.
    """
    try:
        service = GitHubProtectionService(github_token=request.github_token)

        success, message = service.report_status_check(
            owner=request.owner,
            repo=request.repo,
            commit_sha=request.commit_sha,
            check_name=request.check_name,
            status=request.status,
            conclusion=request.conclusion,
            details_url=request.details_url,
            output=request.output
        )

        if not success:
            raise HTTPException(status_code=500, detail=message)

        return ReportCheckResponse(
            success=True,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to report status check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=ValidateComplianceResponse)
async def validate_compliance(
    request: ValidateComplianceRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Validate that a commit meets all Iron Grip requirements

    Checks:
    - Dafny verification passed
    - Drift detection passed
    - Component architecture valid
    - Call graph compliance met
    - Proof ledger integrity verified
    """
    try:
        service = GitHubProtectionService(github_token=request.github_token)

        all_passed, results = service.validate_iron_grip_compliance(
            owner=request.owner,
            repo=request.repo,
            commit_sha=request.commit_sha
        )

        # Convert to response format
        checks_response = {}
        for check_name, check_data in results.get("checks", {}).items():
            if check_data.get("status") == "missing":
                checks_response[check_name] = CheckResult(
                    status="missing",
                    passed=False
                )
            else:
                checks_response[check_name] = CheckResult(
                    status=check_data.get("status", "unknown"),
                    conclusion=check_data.get("conclusion"),
                    passed=check_data.get("passed", False)
                )

        logger.info(
            f"Compliance validation for {request.owner}/{request.repo}@{request.commit_sha[:8]}: "
            f"{'PASS' if all_passed else 'FAIL'}"
        )

        return ValidateComplianceResponse(
            all_passed=all_passed,
            commit=request.commit_sha,
            checks=checks_response,
            missing_checks=results.get("missing_checks", []),
            failed_checks=results.get("failed_checks", [])
        )

    except Exception as e:
        logger.error(f"Failed to validate compliance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def iron_grip_health(
    api_key: str = Depends(get_api_key_from_header)
):
    """
    Check Iron Grip service health
    """
    try:
        service = GitHubProtectionService()

        return {
            "status": "ok",
            "github_token_configured": service.github_token is not None,
            "message": "Iron Grip service operational"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "github_token_configured": False,
            "message": str(e)
        }
