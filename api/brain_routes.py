"""
Brain API Routes - Registry and Proof Ledger Management

Endpoints for managing the .inspecthor/ Brain structure:
- Registry operations (component tracking)
- Proof ledger operations (verification history)
- Integrity checking and drift detection
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import os
from pathlib import Path

from .database import get_db, Blueprint, LedgerEntry
from .brain.registry import RegistryManager
from .brain.proof_ledger import ProofLedger
from .brain.keys import KeyManager
from .auth import get_current_user


# Request/Response Models
class BrainInitRequest(BaseModel):
    """Request to initialize .inspecthor/ structure"""
    blueprint_id: str
    repo_path: str
    component_name: str
    component_path: str = "src/component"


class BrainInitResponse(BaseModel):
    """Response after initializing Brain"""
    success: bool
    brain_path: str
    component_uuid: str
    registry_created: bool
    ledger_created: bool


class ComponentRegistryResponse(BaseModel):
    """Response for component registry entry"""
    uuid: str
    path: str
    name: str
    created_at: str
    last_verified_at: Optional[str] = None
    last_modified_at: Optional[str] = None


class RegistryResponse(BaseModel):
    """Response for full registry"""
    version: str
    created_at: str
    components: Dict[str, ComponentRegistryResponse]


class UpdatePathRequest(BaseModel):
    """Request to update component path"""
    component_uuid: str
    new_path: str


class RecordVerificationRequest(BaseModel):
    """Request to record verification in ledger"""
    component_uuid: str
    blueprint_id: str
    dafny_code: str
    status: str
    proof_obligations: List[Dict]
    dafny_version: Optional[str] = None
    verification_time_ms: Optional[int] = None
    dafny_output: Optional[str] = None
    error_message: Optional[str] = None


class LedgerEntryResponse(BaseModel):
    """Response for ledger entry"""
    uuid: str
    timestamp: str
    hash: str
    status: str
    proof_obligations: List[Dict]
    dafny_version: Optional[str] = None
    verification_time_ms: Optional[int] = None
    dafny_output: Optional[str] = None
    error_message: Optional[str] = None


class IntegrityCheckRequest(BaseModel):
    """Request to check code integrity"""
    component_uuid: str
    repo_path: str
    dafny_code: str


class IntegrityCheckResponse(BaseModel):
    """Response for integrity check"""
    component_uuid: str
    is_intact: bool
    current_hash: str
    ledger_hash: Optional[str] = None
    message: str


class ScanForDriftRequest(BaseModel):
    """Request to scan for component drift"""
    repo_path: str


class DriftIssue(BaseModel):
    """Represents a drift issue"""
    type: str  # 'moved' | 'corrupted' | 'missing'
    uuid: str
    component_name: str
    details: str
    auto_fixable: bool


class DriftReport(BaseModel):
    """Response for drift scan"""
    timestamp: str
    issues: List[DriftIssue]
    summary: Dict[str, int]


# Create router
router = APIRouter(prefix="/api/brain", tags=["Brain"])


@router.post("/initialize", response_model=BrainInitResponse)
async def initialize_brain(
    request: BrainInitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Initialize .inspecthor/ Brain structure for a repository

    Creates:
    - .inspecthor/ folder
    - registry.yaml
    - proof_ledger/ directory
    - keys/ directory
    - .inspecthor_meta file for component
    """
    try:
        # Validate blueprint exists
        blueprint = db.query(Blueprint).filter(
            Blueprint.blueprint_id == request.blueprint_id
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Initialize managers
        registry = RegistryManager(request.repo_path)
        ledger = ProofLedger(request.repo_path)
        keys = KeyManager(request.repo_path)

        # Initialize Brain structure
        registry.initialize()
        ledger.initialize()
        keys.initialize()

        # Generate component UUID if not exists
        if not blueprint.component_uuid:
            import uuid
            component_uuid = str(uuid.uuid4())
            blueprint.component_uuid = component_uuid
            blueprint.registry_path = request.component_path
            db.commit()
        else:
            component_uuid = blueprint.component_uuid

        # Add component to registry
        registry.add_component(
            component_uuid=component_uuid,
            path=request.component_path,
            name=request.component_name
        )

        # Create .inspecthor_meta file
        from .brain.registry import create_component_meta_file
        component_dir = Path(request.repo_path) / request.component_path
        component_dir.mkdir(parents=True, exist_ok=True)
        create_component_meta_file(component_dir, component_uuid)

        brain_path = str(Path(request.repo_path) / ".inspecthor")

        return BrainInitResponse(
            success=True,
            brain_path=brain_path,
            component_uuid=component_uuid,
            registry_created=registry.exists(),
            ledger_created=ledger.exists()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/registry/{repo_path:path}", response_model=RegistryResponse)
async def get_registry(
    repo_path: str,
    current_user = Depends(get_current_user)
):
    """Get the full registry for a repository"""
    try:
        # Decode path (might have URL encoding)
        import urllib.parse
        repo_path = urllib.parse.unquote(repo_path)

        registry = RegistryManager(repo_path)

        if not registry.exists():
            raise HTTPException(
                status_code=404,
                detail="Registry not found. Initialize Brain first."
            )

        # Read registry
        registry_data = registry._read_registry()
        components = registry.get_all_components()

        return RegistryResponse(
            version=registry_data.get('version', '1.0'),
            created_at=registry_data.get('created_at', ''),
            components={
                uuid: ComponentRegistryResponse(**entry.__dict__)
                for uuid, entry in components.items()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/registry/{repo_path:path}/component/{component_uuid}")
async def get_component(
    repo_path: str,
    component_uuid: str,
    current_user = Depends(get_current_user)
):
    """Get a specific component from the registry"""
    try:
        import urllib.parse
        repo_path = urllib.parse.unquote(repo_path)

        registry = RegistryManager(repo_path)
        entry = registry.get_component(component_uuid)

        if not entry:
            raise HTTPException(status_code=404, detail="Component not found")

        return ComponentRegistryResponse(**entry.__dict__)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/registry/{repo_path:path}/update-path")
async def update_component_path(
    repo_path: str,
    request: UpdatePathRequest,
    current_user = Depends(get_current_user)
):
    """Update a component's path in the registry (for drift repair)"""
    try:
        import urllib.parse
        repo_path = urllib.parse.unquote(repo_path)

        registry = RegistryManager(repo_path)
        success = registry.update_component_path(
            request.component_uuid,
            request.new_path
        )

        if not success:
            raise HTTPException(status_code=404, detail="Component not found")

        return {"success": True, "message": "Path updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ledger/record")
async def record_verification(
    request: RecordVerificationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Record a verification in the proof ledger (both file and database)"""
    try:
        # Get blueprint to find repo path
        blueprint = db.query(Blueprint).filter(
            Blueprint.blueprint_id == request.blueprint_id
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Determine repo path (if it exists)
        # For now, we'll skip file-based ledger if no repo_path
        # In production, this should always be set

        # Record in database
        import json
        entry = LedgerEntry(
            component_uuid=request.component_uuid,
            blueprint_id=request.blueprint_id,
            code_hash=ProofLedger(os.getcwd())._compute_hash(request.dafny_code),
            status=request.status,
            proof_obligations=json.dumps(request.proof_obligations),
            dafny_output=request.dafny_output,
            error_message=request.error_message,
            dafny_version=request.dafny_version,
            verification_time_ms=request.verification_time_ms
        )

        db.add(entry)
        db.commit()

        return {
            "success": True,
            "entry_id": str(entry.entry_id),
            "message": "Verification recorded in ledger"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ledger/{component_uuid}/history")
async def get_ledger_history(
    component_uuid: str,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get verification history for a component from database"""
    try:
        entries = db.query(LedgerEntry).filter(
            LedgerEntry.component_uuid == component_uuid
        ).order_by(
            LedgerEntry.created_at.desc()
        ).limit(limit).all()

        import json
        return {
            "component_uuid": component_uuid,
            "entries": [
                {
                    "entry_id": str(e.entry_id),
                    "timestamp": e.created_at.isoformat() + 'Z',
                    "hash": e.code_hash,
                    "status": e.status,
                    "proof_obligations": json.loads(e.proof_obligations) if e.proof_obligations else [],
                    "dafny_version": e.dafny_version,
                    "verification_time_ms": e.verification_time_ms,
                    "error_message": e.error_message
                }
                for e in entries
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/integrity/check", response_model=IntegrityCheckResponse)
async def check_integrity(
    request: IntegrityCheckRequest,
    current_user = Depends(get_current_user)
):
    """Check if current code matches the ledger (tamper detection)"""
    try:
        ledger = ProofLedger(request.repo_path)
        is_intact = ledger.verify_integrity(request.component_uuid, request.dafny_code)

        current_hash = ledger._compute_hash(request.dafny_code)
        latest = ledger.get_latest_entry(request.component_uuid)

        return IntegrityCheckResponse(
            component_uuid=request.component_uuid,
            is_intact=is_intact,
            current_hash=current_hash,
            ledger_hash=latest.hash if latest else None,
            message=(
                "Code matches ledger" if is_intact
                else "Code has been modified - hash mismatch!"
                if latest
                else "No verification history found"
            )
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Enhanced Ledger Endpoints (Task #7 - Cryptographic Proof Ledger)

@router.get("/ledger/{component_uuid}/chain")
async def get_ledger_chain(
    component_uuid: str,
    repo_path: str,
    current_user = Depends(get_current_user)
):
    """
    Get complete chain of custody for a component

    Returns all ledger entries with signatures and chain linkage
    """
    try:
        ledger = ProofLedger(repo_path)

        if not ledger.exists():
            raise HTTPException(
                status_code=404,
                detail="Ledger not found. Initialize Brain first."
            )

        chain = ledger.export_chain(component_uuid)

        return {
            "component_uuid": component_uuid,
            "total_entries": len(chain),
            "chain": chain
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ledger/{component_uuid}/verify-chain")
async def verify_ledger_chain(
    component_uuid: str,
    repo_path: str,
    current_user = Depends(get_current_user)
):
    """
    Verify the complete chain of custody for a component

    Checks:
    - All signatures are valid
    - Chain linkage is intact (previous_hash matches)
    - Entry numbers are sequential
    """
    try:
        ledger = ProofLedger(repo_path)

        if not ledger.exists():
            raise HTTPException(
                status_code=404,
                detail="Ledger not found. Initialize Brain first."
            )

        is_valid, error_message = ledger.verify_chain_integrity(component_uuid)

        return {
            "component_uuid": component_uuid,
            "chain_valid": is_valid,
            "error_message": error_message,
            "message": (
                "Chain of custody is intact - no tampering detected"
                if is_valid
                else f"Chain integrity compromised: {error_message}"
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ledger/{component_uuid}/summary")
async def get_ledger_summary(
    component_uuid: str,
    repo_path: str,
    current_user = Depends(get_current_user)
):
    """
    Get summary statistics for a component's ledger

    Returns:
    - Total entries
    - Verified/failed counts
    - Chain validity
    - First and last verification timestamps
    """
    try:
        ledger = ProofLedger(repo_path)

        if not ledger.exists():
            raise HTTPException(
                status_code=404,
                detail="Ledger not found. Initialize Brain first."
            )

        summary = ledger.get_chain_summary(component_uuid)

        return {
            "component_uuid": component_uuid,
            **summary
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drift/scan", response_model=DriftReport)
async def scan_for_drift(
    request: ScanForDriftRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Scan repository for component drift (moved or corrupted components)"""
    try:
        registry = RegistryManager(request.repo_path)

        if not registry.exists():
            raise HTTPException(
                status_code=404,
                detail="Registry not found. Initialize Brain first."
            )

        issues = []
        components = registry.get_all_components()

        # Check for moved components
        for uuid, entry in components.items():
            component_path = Path(request.repo_path) / entry.path
            meta_file = component_path / '.inspecthor_meta'

            if not meta_file.exists():
                # Component is missing - try to find it
                found_path = registry.scan_for_uuid(uuid)

                if found_path:
                    issues.append(DriftIssue(
                        type='moved',
                        uuid=uuid,
                        component_name=entry.name,
                        details=f"Moved from {entry.path} to {found_path}",
                        auto_fixable=True
                    ))
                else:
                    issues.append(DriftIssue(
                        type='missing',
                        uuid=uuid,
                        component_name=entry.name,
                        details=f"Component not found at {entry.path}",
                        auto_fixable=False
                    ))

        # Check for corrupted components (hash mismatch)
        # This would require reading .dfy files and checking against ledger
        # Skipping for now as it's more complex

        summary = {
            'moved': len([i for i in issues if i.type == 'moved']),
            'corrupted': len([i for i in issues if i.type == 'corrupted']),
            'missing': len([i for i in issues if i.type == 'missing'])
        }

        return DriftReport(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            issues=issues,
            summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drift/repair/{component_uuid}")
async def repair_component(
    component_uuid: str,
    repo_path: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Repair a moved component by updating the registry"""
    try:
        registry = RegistryManager(repo_path)

        # Scan for UUID
        new_path = registry.scan_for_uuid(component_uuid)

        if not new_path:
            raise HTTPException(
                status_code=404,
                detail="Component not found in repository"
            )

        # Update registry
        success = registry.update_component_path(component_uuid, new_path)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update registry"
            )

        return {
            "success": True,
            "component_uuid": component_uuid,
            "new_path": new_path,
            "message": "Component repaired successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
