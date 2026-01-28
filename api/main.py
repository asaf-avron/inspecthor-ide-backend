"""
Guardian Gateway - FastAPI Backend
Main application entry point for the REST API
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow import run_triage, run_structuring
from core.auditor import SpecAuditor
from api.models import (
    GenerateSpecRequest,
    GenerateSpecResponse,
    VerifyDafnyRequest,
    VerifyDafnyResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    Gap,
    GapLocation,
    Ambiguity,
    TraceabilityEntry,
    SpecStatistics,
    UnitInfo,
    FindGapsRequest,
    FindGapsResponse,
    RefineSpecRequest,
    RefineSpecResponse,
)
from api.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestLoggingMiddleware, SecurityScannerMiddleware
from api.database import init_db, get_db, File as DBFile, UnitLink as DBUnitLink, Project as DBProject
from api import files
from api.files import get_api_key_from_header, get_project_owner_filter, hash_api_key
from api import verification
from api import deconstruct
from api.deconstruct import UnitIdentifier, extract_content_by_lines, create_unit_filename
from api import projects
from api import auth
from api.auth import get_current_user
from api.github import webhooks as github_webhooks
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import re
import os
from datetime import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        init_db()
        logging.info("Database initialized")
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        raise
    yield
    # Shutdown (if needed)
    pass


app = FastAPI(
    title="Guardian Gateway API",
    description="REST API for formal specification verification",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration - get allowed origins from environment
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware
# Note: Middleware is applied in reverse order (last added = first executed)
# Order: SecurityScannerMiddleware -> RequestLoggingMiddleware -> RateLimitMiddleware -> APIKeyMiddleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "300")))
app.add_middleware(APIKeyMiddleware)
app.add_middleware(SecurityScannerMiddleware)  # Runs first - blocks scanners before they hit rate limiting


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors for debugging"""
    body = await request.body()
    logging.error(f"Validation error on {request.url.path}: {exc.errors()}")
    logging.error(f"Request body: {body.decode('utf-8') if body else 'empty'}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(verification.router)
app.include_router(deconstruct.router)
app.include_router(projects.router)
app.include_router(github_webhooks.router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    auditor = SpecAuditor()
    
    # Check if Dafny is available
    import shutil
    dafny_available = shutil.which("dafny") is not None
    
    return HealthResponse(
        status="ok",
        gemini_configured=auditor.is_configured(),
        dafny_available=dafny_available,
    )


@app.post("/api/generate/spec", response_model=GenerateSpecResponse)
async def generate_spec(
    request: GenerateSpecRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Generate formal specification from English requirements.
    Combines Triage + Structure + Audit stages.
    Automatically assesses units and creates subfolder structure if units are found.
    """
    # Stage 1: Triage
    triage_result = run_triage(request.english_spec)
    if triage_result.error:
        raise HTTPException(status_code=400, detail=triage_result.error)
    
    # Stage 2: Structure
    structure_result = run_structuring(request.english_spec)
    if structure_result.error:
        raise HTTPException(status_code=400, detail=structure_result.error)
    
    # Filename suggestion (if generic filename detected)
    suggested_filename = None
    current_filename = request.current_filename or ""
    
    # Check if filename is generic (untitled-*, new-file-*, etc.)
    is_generic = False
    if current_filename:
        generic_patterns = [r'^untitled-', r'^new-file-', r'^untitled\d+', r'^new\d+']
        is_generic = any(re.match(pattern, current_filename.lower()) for pattern in generic_patterns)
    
    if is_generic:
        # Suggest filename using Gemini
        auditor_temp = SpecAuditor()
        if auditor_temp.is_configured():
            try:
                prompt = f"""Based on this specification, suggest a concise, descriptive filename (without extension).
Return ONLY the filename, no path, no extension, no quotes, no markdown.
Examples: token-minting-spec, authentication-requirements, payment-processing

SPECIFICATION:
{structure_result.structured_spec[:2000]}

Filename:"""
                response = auditor_temp._client.models.generate_content(
                    model=auditor_temp._model,
                    contents=prompt
                )
                suggested_filename = response.text.strip().strip('"').strip("'").strip()
                # Clean up any markdown or extra text
                if suggested_filename.startswith("```"):
                    suggested_filename = suggested_filename.split("\n")[0].replace("```", "").strip()
                suggested_filename = re.sub(r'[^a-z0-9-]', '', suggested_filename.lower())[:50]
            except Exception as e:
                logging.warning(f"Filename suggestion failed: {e}")
                suggested_filename = None
    
    # Stage 3: Audit (only for Dafny generation, not for gap detection)
    # Gap detection is now separate via /api/generate/find-gaps endpoint
    auditor = SpecAuditor()
    if not auditor.is_configured():
        raise HTTPException(
            status_code=500,
            detail=auditor.get_configuration_error()
        )
    
    # Audit is needed for Dafny generation (both for units and fallback)
    audit_result = auditor.audit_spec(structure_result.structured_spec)
    if audit_result.error:
        raise HTTPException(status_code=500, detail=audit_result.error)
    
    # Empty gaps/ambiguities - gap detection is now separate
    enhanced_gaps = []
    enhanced_ambiguities = []
    
    # Enhanced traceability matrix (still needed to link requirements to Dafny code)
    enhanced_traceability = []
    for idx, entry in enumerate(audit_result.traceability_matrix):
        enhanced_traceability.append(TraceabilityEntry(
            id=entry.id,
            source_text=entry.source_text,
            code_line=entry.code_line,
            line_number=None,
            status=entry.status if entry.status in ["mapped", "partial", "missing"] else "mapped",
            confidence=0.9
        ))
    
    # Calculate statistics based on traceability (not gaps)
    total_reqs = len(enhanced_traceability)
    mapped_reqs = sum(1 for e in enhanced_traceability if e.status == "mapped")
    coverage = (mapped_reqs / total_reqs * 100) if total_reqs > 0 else 0.0
    
    statistics = SpecStatistics(
        total_requirements=total_reqs,
        mapped_requirements=mapped_reqs,
        coverage_percentage=round(coverage, 2),
        total_gaps=0,  # Gaps are now separate
        critical_gaps=0
    )
    
    # Unit deconstruction logic
    units_created = None
    subfolder_name = None
    
    # Only proceed with unit deconstruction if project_id and source_file_id are provided
    if request.project_id and request.source_file_id:
        try:
            # Verify project ownership
            api_key_hash_value = hash_api_key(api_key) if api_key else None
            owner_filter = get_project_owner_filter(current_user, api_key_hash_value)
            project = db.query(DBProject).filter(
                DBProject.project_id == request.project_id,
                owner_filter
            ).first()
            
            if not project:
                logging.warning(f"Project {request.project_id} not found or unauthorized for unit deconstruction")
            else:
                # Load source file
                source_file = db.query(DBFile).filter(
                    DBFile.file_id == request.source_file_id,
                    DBFile.project_id == request.project_id
                ).first()
                
                if source_file and source_file.file_type == 'md':
                    # Identify units
                    identifier = UnitIdentifier()
                    try:
                        unit_candidates = identifier.identify_units(source_file.content)
                        
                        if unit_candidates and len(unit_candidates) > 0:
                            # Determine subfolder name
                            filename_to_use = suggested_filename or current_filename or "spec"
                            # Remove extension if present
                            filename_base = os.path.splitext(filename_to_use)[0] if '.' in filename_to_use else filename_to_use
                            subfolder_name = f"{filename_base}-units"
                            
                            # Process each unit
                            created_units = []
                            successful_count = 0
                            
                            for idx, candidate in enumerate(unit_candidates, start=1):
                                try:
                                    # Extract unit content
                                    unit_content = extract_content_by_lines(
                                        source_file.content,
                                        candidate.line_range[0],
                                        candidate.line_range[1]
                                    )
                                    
                                    # Structure unit content
                                    unit_structure_result = run_structuring(unit_content)
                                    if unit_structure_result.error:
                                        logging.warning(f"Unit {idx} structuring failed: {unit_structure_result.error}")
                                        continue
                                    
                                    # Audit unit spec to get formal spec with anchors and Dafny
                                    unit_audit_result = auditor.audit_spec(unit_structure_result.structured_spec)
                                    if unit_audit_result.error:
                                        logging.warning(f"Unit {idx} audit failed: {unit_audit_result.error}")
                                        continue
                                    
                                    dafny_code = unit_audit_result.dafny_skeleton
                                    formal_spec = unit_audit_result.tagged_spec or unit_structure_result.structured_spec
                                    
                                    # Create filenames with subfolder
                                    unit_filename = create_unit_filename(idx, candidate.title, ".unit.md", subfolder_name)
                                    dafny_filename = create_unit_filename(idx, candidate.title, ".dfy", subfolder_name)
                                    
                                    # Create unit markdown content
                                    unit_markdown = f"""# Unit: {candidate.title}

## Description
{candidate.description}

## Requirements
{chr(10).join(f"- {req}" for req in candidate.requirements)}

## Dependencies
{chr(10).join(f"- {dep}" for dep in candidate.dependencies) if candidate.dependencies else "None"}

## Formal Specification
{formal_spec}
"""
                                    
                                    # Save unit markdown file
                                    unit_file_id = str(uuid.uuid4())
                                    unit_file = DBFile(
                                        file_id=unit_file_id,
                                        project_id=source_file.project_id,
                                        filename=unit_filename,
                                        content=unit_markdown,
                                        file_type='unit',
                                        size_bytes=len(unit_markdown.encode('utf-8'))
                                    )
                                    db.add(unit_file)
                                    
                                    # Save Dafny file
                                    dafny_file_id = str(uuid.uuid4())
                                    dafny_file = DBFile(
                                        file_id=dafny_file_id,
                                        project_id=source_file.project_id,
                                        filename=dafny_filename,
                                        content=dafny_code,
                                        file_type='dfy',
                                        size_bytes=len(dafny_code.encode('utf-8'))
                                    )
                                    db.add(dafny_file)
                                    
                                    # Create unit link
                                    link_id = str(uuid.uuid4())
                                    unit_link = DBUnitLink(
                                        link_id=link_id,
                                        root_file_id=source_file.file_id,
                                        unit_file_id=unit_file_id,
                                        dafny_file_id=dafny_file_id,
                                        start_line=candidate.line_range[0],
                                        end_line=candidate.line_range[1],
                                        title=candidate.title,
                                        verification_status='unknown'
                                    )
                                    db.add(unit_link)
                                    
                                    db.commit()
                                    
                                    # Add to response
                                    created_units.append(UnitInfo(
                                        unit_id=unit_file_id,
                                        unit_filename=unit_filename,
                                        dafny_filename=dafny_filename,
                                        title=candidate.title,
                                        description=candidate.description,
                                        requirements=candidate.requirements,
                                        dafny_code=dafny_code,
                                        line_range=candidate.line_range
                                    ))
                                    
                                    successful_count += 1
                                    
                                except Exception as e:
                                    logging.error(f"Failed to create unit {idx}: {e}")
                                    db.rollback()
                                    continue
                            
                            if created_units:
                                units_created = created_units
                                logging.info(f"Created {successful_count} units in subfolder {subfolder_name}")
                        
                    except Exception as e:
                        logging.warning(f"Unit identification failed: {e}")
                        # Fall back to single Dafny file
                        pass
                        
        except Exception as e:
            logging.error(f"Unit deconstruction error: {e}")
            # Fall back to single Dafny file
    
    # If units were created, don't return root-level Dafny skeleton
    # Otherwise, return Dafny for the root spec
    dafny_skeleton_to_return = "" if units_created else audit_result.dafny_skeleton
    
    return GenerateSpecResponse(
        triage={
            "doc_type": triage_result.doc_type.value if triage_result.doc_type else "junk",
            "confidence": triage_result.confidence,
            "detected_patterns": []  # Can be enhanced later
        },
        structured_spec=structure_result.structured_spec,
        dafny_skeleton=dafny_skeleton_to_return,
        gaps=enhanced_gaps,
        ambiguities=enhanced_ambiguities,
        traceability_matrix=enhanced_traceability,
        statistics=statistics,
        suggested_filename=suggested_filename,
        units_created=units_created,
        subfolder_name=subfolder_name
    )


@app.post("/api/generate/find-gaps", response_model=FindGapsResponse)
async def find_gaps(
    request: FindGapsRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Find gaps and ambiguities in a specification without generating Dafny code.
    Used for the refinement flow where users can fix gaps before generating formal specs.
    """
    # Stage 1: Structure the spec
    structure_result = run_structuring(request.spec)
    if structure_result.error:
        raise HTTPException(status_code=400, detail=structure_result.error)
    
    # Stage 2: Audit to find gaps
    auditor = SpecAuditor()
    if not auditor.is_configured():
        raise HTTPException(
            status_code=500,
            detail=auditor.get_configuration_error()
        )
    
    audit_result = auditor.audit_spec(structure_result.structured_spec)
    if audit_result.error:
        raise HTTPException(status_code=500, detail=audit_result.error)
    
    # Enhanced gap processing with IDs and locations
    enhanced_gaps = []
    for idx, gap in enumerate(audit_result.gaps):
        enhanced_gaps.append(Gap(
            id=f"GAP-{idx+1:03d}",
            severity=gap.severity if gap.severity in ["critical", "high", "medium", "low"] else "medium",
            category="incomplete-spec",
            description=gap.description,
            location=GapLocation(line=None, column=None, file=None),
            suggestion=f"Consider adding more details about: {gap.description[:50]}...",
            code_snippet=None
        ))
    
    # Enhanced ambiguities with IDs
    enhanced_ambiguities = []
    for idx, amb_text in enumerate(audit_result.ambiguities):
        enhanced_ambiguities.append(Ambiguity(
            id=f"AMB-{idx+1:03d}",
            text=amb_text,
            possible_interpretations=["Interpretation A", "Interpretation B"],
            recommendation="Please clarify this requirement"
        ))
    
    # Calculate statistics
    total_reqs = len(audit_result.traceability_matrix)
    mapped_reqs = sum(1 for entry in audit_result.traceability_matrix if entry.status == "mapped")
    coverage = (mapped_reqs / total_reqs * 100) if total_reqs > 0 else 0.0
    critical_gaps = sum(1 for g in enhanced_gaps if g.severity == "critical")
    
    statistics = SpecStatistics(
        total_requirements=total_reqs,
        mapped_requirements=mapped_reqs,
        coverage_percentage=round(coverage, 2),
        total_gaps=len(enhanced_gaps),
        critical_gaps=critical_gaps
    )
    
    return FindGapsResponse(
        gaps=enhanced_gaps,
        ambiguities=enhanced_ambiguities,
        statistics=statistics
    )


@app.post("/api/generate/refine-spec", response_model=RefineSpecResponse)
async def refine_spec(
    request: RefineSpecRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user = Depends(get_current_user)
):
    """
    Refine a specification by applying gap suggestions.
    Uses Gemini to generate refined spec text with selected gap suggestions applied.
    """
    auditor = SpecAuditor()
    
    if not auditor.is_configured():
        raise HTTPException(
            status_code=500,
            detail=auditor.get_configuration_error()
        )
    
    # Filter gaps to apply
    gaps_to_apply = request.gaps
    if request.apply_gap_ids:
        gaps_to_apply = [gap for gap in request.gaps if gap.id in request.apply_gap_ids]
    
    if not gaps_to_apply:
        # No gaps to apply, return original spec
        return RefineSpecResponse(
            refined_spec=request.spec,
            applied_gaps=[]
        )
    
    # Build prompt for Gemini to refine the spec
    gap_descriptions = "\n".join([
        f"- {gap.id} ({gap.severity}): {gap.description}\n  Suggestion: {gap.suggestion or 'No specific suggestion'}"
        for gap in gaps_to_apply
    ])
    
    prompt = f"""You are refining a formal specification document based on identified gaps.

ORIGINAL SPECIFICATION:
{request.spec}

IDENTIFIED GAPS TO ADDRESS:
{gap_descriptions}

TASK:
Refine the original specification by addressing the gaps listed above. Apply the suggestions provided for each gap.
- Keep the overall structure and style of the original specification
- Integrate the improvements naturally into the existing text
- Maintain consistency with the original document's tone and format
- Do not add new sections unless necessary to address the gaps
- Preserve all existing content that is not related to the gaps

Return the complete refined specification:
"""
    
    try:
        response = auditor._client.models.generate_content(
            model=auditor._model,
            contents=prompt
        )
        refined_spec = response.text.strip()
        
        # Clean up markdown code blocks if present
        if refined_spec.startswith("```"):
            lines = refined_spec.split("\n")
            # Remove first line (```markdown or similar)
            if len(lines) > 1:
                lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            refined_spec = "\n".join(lines)
        
        return RefineSpecResponse(
            refined_spec=refined_spec,
            applied_gaps=gaps_to_apply
        )
    except Exception as e:
        logging.error(f"Spec refinement failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refine specification: {str(e)}"
        )


@app.post("/api/assistant/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """AI assistant for debugging verification failures"""
    auditor = SpecAuditor()
    
    if not auditor.is_configured():
        raise HTTPException(
            status_code=500,
            detail=auditor.get_configuration_error()
        )
    
    # For now, return a simple response
    # TODO: Implement full conversation with context
    return ChatResponse(
        content=f"I received your message: {request.message}. This is a placeholder response.",
        suggestions=["Review the specification", "Check for ambiguities", "Run verification"],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
