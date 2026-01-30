"""
API routes for the Trust Registry (ground truth for Dafny specs).
"""

from fastapi import APIRouter, HTTPException

from api.models import RegisterSpecRequest, SpecResponse
from api.trust_registry import get_trust_registry

router = APIRouter(prefix="/api/trust-registry", tags=["trust-registry"])


@router.post("/specs", response_model=SpecResponse)
async def register_spec(request: RegisterSpecRequest):
    """Register a Dafny spec as ground truth. Overwrites if spec_id exists."""
    registry = get_trust_registry()
    entry = registry.register(
        spec_id=request.spec_id,
        content=request.content,
        metadata=request.metadata,
    )
    return SpecResponse(
        spec_id=entry.spec_id,
        content=entry.content,
        created_at=entry.created_at,
        metadata=entry.metadata,
    )


@router.get("/specs/{spec_id}", response_model=SpecResponse)
async def get_spec(spec_id: str):
    """Get a spec by id from the Trust Registry."""
    registry = get_trust_registry()
    entry = registry.get(spec_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Spec not found: {spec_id}")
    return SpecResponse(
        spec_id=entry.spec_id,
        content=entry.content,
        created_at=entry.created_at,
        metadata=entry.metadata,
    )


@router.get("/specs")
async def list_specs():
    """List all spec ids in the Trust Registry."""
    registry = get_trust_registry()
    entries = registry.list_specs()
    return {"spec_ids": [e.spec_id for e in entries], "total": len(entries)}
