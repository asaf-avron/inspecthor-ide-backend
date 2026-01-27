"""
Guardian Gateway - FastAPI Backend
Main application entry point for the REST API
"""

from fastapi import FastAPI, HTTPException, Request
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
)
from api.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestLoggingMiddleware, SecurityScannerMiddleware
from api.database import init_db
from api import files
from api import verification
from api import deconstruct
from api import projects
from api import auth
from api.github import webhooks as github_webhooks


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
app.add_middleware(RateLimitMiddleware, requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))
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
async def generate_spec(request: GenerateSpecRequest):
    """
    Generate formal specification from English requirements.
    Combines Triage + Structure + Audit stages.
    """
    # Stage 1: Triage
    triage_result = run_triage(request.english_spec)
    if triage_result.error:
        raise HTTPException(status_code=400, detail=triage_result.error)
    
    # Stage 2: Structure
    structure_result = run_structuring(request.english_spec)
    if structure_result.error:
        raise HTTPException(status_code=400, detail=structure_result.error)
    
    # Stage 3: Audit
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
            category="incomplete-spec",  # Default category, can be enhanced later
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
    
    # Enhanced traceability matrix
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
    
    # Calculate statistics
    total_reqs = len(enhanced_traceability)
    mapped_reqs = sum(1 for e in enhanced_traceability if e.status == "mapped")
    coverage = (mapped_reqs / total_reqs * 100) if total_reqs > 0 else 0
    critical_gaps = sum(1 for g in enhanced_gaps if g.severity == "critical")
    
    statistics = SpecStatistics(
        total_requirements=total_reqs,
        mapped_requirements=mapped_reqs,
        coverage_percentage=round(coverage, 2),
        total_gaps=len(enhanced_gaps),
        critical_gaps=critical_gaps
    )
    
    return GenerateSpecResponse(
        triage={
            "doc_type": triage_result.doc_type.value if triage_result.doc_type else "junk",
            "confidence": triage_result.confidence,
            "detected_patterns": []  # Can be enhanced later
        },
        structured_spec=structure_result.structured_spec,
        dafny_skeleton=audit_result.dafny_skeleton,
        gaps=enhanced_gaps,
        ambiguities=enhanced_ambiguities,
        traceability_matrix=enhanced_traceability,
        statistics=statistics
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
