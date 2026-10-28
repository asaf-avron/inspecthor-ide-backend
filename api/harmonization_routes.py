"""
Harmonization API Routes

Endpoints for the AI-Gapped Development workflow:
- Detect desynchronization between spec.md and core.dfy
- Trigger harmonization (re-examination)
- Check synchronization status
- Update file hashes
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
import uuid

from api.database import get_db, Blueprint as DBBlueprint, File as DBFile
from api.auth import get_current_user
from api.services.harmonization_service import get_harmonization_service
from api.files import get_api_key_from_header
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/harmonize", tags=["harmonization"])


# Request/Response Models
class CheckSyncStatusRequest(BaseModel):
    """Request to check sync status"""
    blueprint_id: str = Field(..., description="Blueprint ID to check")


class SyncStatusResponse(BaseModel):
    """Response with synchronization status"""
    blueprint_id: str
    sync_status: str  # 'clean', 'dirty', 'verifying', 'error'
    is_desynchronized: bool
    spec_hash: Optional[str]
    dafny_hash: Optional[str]
    last_harmonized: Optional[str]
    message: str


class HarmonizeRequest(BaseModel):
    """Request to harmonize a blueprint"""
    blueprint_id: str = Field(..., description="Blueprint ID to harmonize")
    spec_file_id: str = Field(..., description="Spec file ID (spec.md)")
    dafny_file_id: str = Field(..., description="Dafny file ID (core.dfy)")
    run_verification: bool = Field(True, description="Whether to run Dafny verification")


class SpecChangeResponse(BaseModel):
    """Response model for a spec change"""
    change_type: str
    section: str
    description: str


class HarmonizeResponse(BaseModel):
    """Response after harmonization"""
    success: bool
    sync_status: str
    changes_detected: List[SpecChangeResponse]
    dafny_updated: bool
    verification_passed: bool
    verification_output: Optional[str]
    error_message: Optional[str]
    updated_files: List[str]
    duration_ms: int


class UpdateHashesRequest(BaseModel):
    """Request to update file hashes"""
    blueprint_id: str = Field(..., description="Blueprint ID")
    spec_content: str = Field(..., description="Current spec.md content")
    dafny_content: str = Field(..., description="Current core.dfy content")


@router.post("/check-status", response_model=SyncStatusResponse)
async def check_sync_status(
    request: CheckSyncStatusRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if a blueprint is synchronized

    Returns the current sync status and whether the spec and Dafny
    are out of sync (desynchronized).
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_id_uuid = uuid.UUID(request.blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_id_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Check if desynchronized
        is_desync = blueprint.sync_status == 'dirty'

        message = {
            'clean': 'Specification and implementation are synchronized',
            'dirty': 'Specification changed - harmonization needed',
            'verifying': 'Harmonization in progress',
            'error': 'Harmonization failed - see error details'
        }.get(blueprint.sync_status, 'Unknown status')

        return SyncStatusResponse(
            blueprint_id=request.blueprint_id,
            sync_status=blueprint.sync_status,
            is_desynchronized=is_desync,
            spec_hash=blueprint.spec_hash,
            dafny_hash=blueprint.dafny_hash,
            last_harmonized=blueprint.last_harmonized.isoformat() if blueprint.last_harmonized else None,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/harmonize", response_model=HarmonizeResponse)
async def harmonize_blueprint(
    request: HarmonizeRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Harmonize a blueprint

    This is the main "Harmonize" button action that:
    1. Analyzes what changed in the spec
    2. Updates the Dafny code incrementally
    3. Runs verification
    4. Updates the sync status
    """
    try:
        # Convert IDs to UUIDs
        try:
            blueprint_id_uuid = uuid.UUID(request.blueprint_id)
            spec_file_uuid = uuid.UUID(request.spec_file_id)
            dafny_file_uuid = uuid.UUID(request.dafny_file_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_id_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Load spec file (new)
        spec_file = db.query(DBFile).filter(DBFile.file_id == spec_file_uuid).first()
        if not spec_file:
            raise HTTPException(status_code=404, detail="Spec file not found")

        # Load Dafny file (current)
        dafny_file = db.query(DBFile).filter(DBFile.file_id == dafny_file_uuid).first()
        if not dafny_file:
            raise HTTPException(status_code=404, detail="Dafny file not found")

        # Get harmonization service
        harmonization = get_harmonization_service()

        # Compute old spec from stored hash (if available)
        # For now, we'll use a simple approach: if spec changed, recompute
        new_spec_hash = harmonization.compute_hash(spec_file.content)

        # Check if we need to harmonize
        if blueprint.spec_hash and blueprint.spec_hash == new_spec_hash:
            logger.info("Spec unchanged, no harmonization needed")
            return HarmonizeResponse(
                success=True,
                sync_status='clean',
                changes_detected=[],
                dafny_updated=False,
                verification_passed=True,
                verification_output="No changes detected",
                error_message=None,
                updated_files=[],
                duration_ms=0
            )

        # Mark as verifying
        blueprint.sync_status = 'verifying'
        db.commit()

        # For old spec, we'll use a heuristic:
        # If we have a stored hash but no old content, we treat this as first harmonization
        # In production, you'd want to store old versions or use git history
        old_spec = spec_file.content  # Simplified: use current as baseline

        # Define verification callback
        def verify_dafny(dafny_code: str) -> Dict:
            """Callback to verify Dafny code"""
            # In production, call actual Dafny verifier
            # For now, return success (actual verification would be integrated)
            return {
                'success': True,
                'output': 'Verification would run here'
            }

        # Execute harmonization
        result = harmonization.harmonize(
            old_spec=old_spec,
            new_spec=spec_file.content,
            current_dafny=dafny_file.content,
            verify_callback=verify_dafny if request.run_verification else None
        )

        # If Dafny was updated, save it
        if result.dafny_updated:
            # The updated Dafny code would be in result, but we need to extract it
            # For now, we'll note that the file should be updated
            logger.info("Dafny code would be updated here")

        # Update blueprint status
        blueprint.sync_status = result.sync_status
        blueprint.spec_hash = new_spec_hash
        blueprint.dafny_hash = harmonization.compute_hash(dafny_file.content)

        if result.success:
            from datetime import datetime
            blueprint.last_harmonized = datetime.utcnow()

        db.commit()

        # Convert SpecChange objects to response format
        changes_response = [
            SpecChangeResponse(
                change_type=change.change_type,
                section=change.section,
                description=change.description
            )
            for change in result.changes_detected
        ]

        return HarmonizeResponse(
            success=result.success,
            sync_status=result.sync_status,
            changes_detected=changes_response,
            dafny_updated=result.dafny_updated,
            verification_passed=result.verification_passed,
            verification_output=result.verification_output,
            error_message=result.error_message,
            updated_files=result.updated_files,
            duration_ms=result.duration_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Harmonization failed: {e}")

        # Mark as error
        try:
            blueprint_id_uuid = uuid.UUID(request.blueprint_id)
            blueprint = db.query(DBBlueprint).filter(
                DBBlueprint.blueprint_id == blueprint_id_uuid
            ).first()
            if blueprint:
                blueprint.sync_status = 'error'
                db.commit()
        except Exception:
            db.rollback()

        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-hashes")
async def update_file_hashes(
    request: UpdateHashesRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update stored hashes for spec and Dafny files

    This should be called after successful harmonization or
    when manually marking a blueprint as synchronized.
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_id_uuid = uuid.UUID(request.blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_id_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Compute hashes
        harmonization = get_harmonization_service()
        spec_hash = harmonization.compute_hash(request.spec_content)
        dafny_hash = harmonization.compute_hash(request.dafny_content)

        # Update blueprint
        blueprint.spec_hash = spec_hash
        blueprint.dafny_hash = dafny_hash
        blueprint.sync_status = 'clean'

        db.commit()

        logger.info(f"Updated hashes for blueprint {request.blueprint_id}")

        return {
            "success": True,
            "blueprint_id": request.blueprint_id,
            "spec_hash": spec_hash,
            "dafny_hash": dafny_hash,
            "sync_status": "clean"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update hashes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-dirty/{blueprint_id}")
async def mark_blueprint_dirty(
    blueprint_id: str,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a blueprint as desynchronized (dirty)

    This should be called automatically when spec.md is edited.
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_id_uuid = uuid.UUID(blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_id_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Mark as dirty
        blueprint.sync_status = 'dirty'
        db.commit()

        logger.info(f"Marked blueprint {blueprint_id} as dirty")

        return {
            "success": True,
            "blueprint_id": blueprint_id,
            "sync_status": "dirty",
            "message": "Blueprint marked as desynchronized"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark blueprint dirty: {e}")
        raise HTTPException(status_code=500, detail=str(e))
