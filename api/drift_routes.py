"""
Drift Detection and Repair API Routes

Endpoints for scanning and repairing component drift.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import os
import logging

from api.database import get_db
from api.auth import get_current_user
from api.files import get_api_key_from_header
from api.services.drift_detector import DriftDetector, DriftIssue, DriftReport, RepairResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drift", tags=["drift-detection"])


# Request/Response Models
class ScanDriftRequest(BaseModel):
    """Request to scan for drift"""
    repo_path: str = Field(..., description="Path to repository root")


class DriftIssueResponse(BaseModel):
    """Response model for a drift issue"""
    issue_type: str
    component_uuid: str
    component_name: str
    expected_path: Optional[str]
    actual_path: Optional[str]
    severity: str
    description: str
    repairable: bool


class DriftReportResponse(BaseModel):
    """Response with drift report"""
    repo_path: str
    scan_timestamp: str
    total_issues: int
    issues_by_type: Dict[str, int]
    issues: List[DriftIssueResponse]
    health_score: float


class RepairRequest(BaseModel):
    """Request to repair a component"""
    repo_path: str = Field(..., description="Path to repository root")
    component_uuid: str = Field(..., description="UUID of component to repair")


class RepairResponse(BaseModel):
    """Response from repair operation"""
    success: bool
    component_uuid: str
    old_path: Optional[str]
    new_path: Optional[str]
    action_taken: str
    message: str


class AutoRepairRequest(BaseModel):
    """Request to auto-repair all repairable issues"""
    repo_path: str = Field(..., description="Path to repository root")


class AutoRepairResponse(BaseModel):
    """Response from auto-repair operation"""
    total_repaired: int
    successful_repairs: int
    failed_repairs: int
    results: List[RepairResponse]


@router.post("/scan", response_model=DriftReportResponse)
async def scan_for_drift(
    request: ScanDriftRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Scan a repository for drift issues

    Detects:
    - Missing components (in registry but file doesn't exist)
    - Moved components (UUID exists but at different path)
    - Corrupted components (hash mismatch with ledger)
    - Orphaned components (exist but not in registry)

    Returns a drift report with health score and list of issues.
    """
    try:
        # Validate repo path
        if not os.path.exists(request.repo_path):
            raise HTTPException(status_code=404, detail="Repository path not found")

        # Check for .inspecthor directory
        inspecthor_path = os.path.join(request.repo_path, '.inspecthor')
        if not os.path.exists(inspecthor_path):
            raise HTTPException(
                status_code=400,
                detail="Repository not initialized - .inspecthor/ directory not found"
            )

        # Create drift detector
        detector = DriftDetector(request.repo_path)

        # Scan for drift
        report = detector.scan_for_drift()

        # Convert to response model
        issues_response = [
            DriftIssueResponse(
                issue_type=issue.issue_type,
                component_uuid=issue.component_uuid,
                component_name=issue.component_name,
                expected_path=issue.expected_path,
                actual_path=issue.actual_path,
                severity=issue.severity,
                description=issue.description,
                repairable=issue.repairable
            )
            for issue in report.issues
        ]

        logger.info(f"Drift scan completed for {request.repo_path}: {report.total_issues} issues")

        return DriftReportResponse(
            repo_path=report.repo_path,
            scan_timestamp=report.scan_timestamp,
            total_issues=report.total_issues,
            issues_by_type=report.issues_by_type,
            issues=issues_response,
            health_score=report.health_score
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to scan for drift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repair", response_model=RepairResponse)
async def repair_component(
    request: RepairRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Repair a specific component

    Automatically detects the type of drift and applies the appropriate fix:
    - Moved components: Updates registry with new path
    - Orphaned components: Adds to registry
    - Missing components: Attempts to find by UUID

    Returns repair result with details of the action taken.
    """
    try:
        # Validate repo path
        if not os.path.exists(request.repo_path):
            raise HTTPException(status_code=404, detail="Repository path not found")

        # Create drift detector
        detector = DriftDetector(request.repo_path)

        # Scan to determine issue type
        report = detector.scan_for_drift()

        # Find the specific issue
        target_issue = None
        for issue in report.issues:
            if issue.component_uuid == request.component_uuid:
                target_issue = issue
                break

        if not target_issue:
            raise HTTPException(
                status_code=404,
                detail=f"No drift issue found for component {request.component_uuid}"
            )

        if not target_issue.repairable:
            raise HTTPException(
                status_code=400,
                detail=f"Component {request.component_uuid} is not auto-repairable: {target_issue.description}"
            )

        # Perform repair based on issue type
        if target_issue.issue_type in ['moved', 'missing']:
            result = detector.repair_moved_component(request.component_uuid)
        elif target_issue.issue_type == 'orphaned':
            result = detector.repair_orphaned_component(request.component_uuid)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown issue type: {target_issue.issue_type}"
            )

        logger.info(f"Repair {'succeeded' if result.success else 'failed'} for {request.component_uuid}")

        return RepairResponse(
            success=result.success,
            component_uuid=result.component_uuid,
            old_path=result.old_path,
            new_path=result.new_path,
            action_taken=result.action_taken,
            message=result.message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to repair component: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-repair", response_model=AutoRepairResponse)
async def auto_repair_all(
    request: AutoRepairRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Automatically repair all repairable drift issues

    Scans the repository and attempts to repair all issues that can be
    automatically fixed. Returns a summary of repair attempts.

    Note: Corrupted components (hash mismatches) cannot be auto-repaired
    and require manual review.
    """
    try:
        # Validate repo path
        if not os.path.exists(request.repo_path):
            raise HTTPException(status_code=404, detail="Repository path not found")

        # Create drift detector
        detector = DriftDetector(request.repo_path)

        # Auto-repair all issues
        results = detector.auto_repair_all()

        # Convert to response model
        results_response = [
            RepairResponse(
                success=result.success,
                component_uuid=result.component_uuid,
                old_path=result.old_path,
                new_path=result.new_path,
                action_taken=result.action_taken,
                message=result.message
            )
            for result in results
        ]

        # Count successes and failures
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        logger.info(f"Auto-repair completed: {successful} successful, {failed} failed")

        return AutoRepairResponse(
            total_repaired=len(results),
            successful_repairs=successful,
            failed_repairs=failed,
            results=results_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to auto-repair: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/{repo_path:path}", response_model=dict)
async def get_repository_health(
    repo_path: str,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get repository health status

    Returns a quick health check without full drift scan.
    Checks if .inspecthor/ exists and registry is valid.
    """
    try:
        # Decode path (FastAPI encodes it)
        repo_path = repo_path.replace('%5C', '\\').replace('%2F', '/')

        if not os.path.exists(repo_path):
            raise HTTPException(status_code=404, detail="Repository path not found")

        # Check for .inspecthor directory
        inspecthor_path = os.path.join(repo_path, '.inspecthor')
        brain_exists = os.path.exists(inspecthor_path)

        if not brain_exists:
            return {
                "healthy": False,
                "brain_initialized": False,
                "message": "Brain not initialized - run /api/brain/initialize"
            }

        # Check registry
        registry_path = os.path.join(inspecthor_path, 'registry.yaml')
        registry_exists = os.path.exists(registry_path)

        if not registry_exists:
            return {
                "healthy": False,
                "brain_initialized": True,
                "registry_exists": False,
                "message": "Registry file missing"
            }

        # Quick scan
        detector = DriftDetector(repo_path)
        report = detector.scan_for_drift()

        return {
            "healthy": report.health_score >= 80.0,
            "brain_initialized": True,
            "registry_exists": True,
            "health_score": report.health_score,
            "total_issues": report.total_issues,
            "critical_issues": report.issues_by_type.get('critical', 0),
            "message": "Repository health check complete"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check repository health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
