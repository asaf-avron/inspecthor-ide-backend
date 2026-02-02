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
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.auditor import SpecAuditor
from api.models import (
    GenerateSpecRequest,
    GenerateSpecResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    FindGapsRequest,
    FindGapsResponse,
    RefineSpecRequest,
    RefineSpecResponse,
)
from api.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestLoggingMiddleware, SecurityScannerMiddleware
from api.database import init_db, get_db
from api import files
from api.files import get_api_key_from_header
from api import verification
from api import deconstruct
from api import projects
from api import auth
from api.auth import get_current_user
from api.github import webhooks as github_webhooks
from api.github import installations as github_installations
from api import blueprints
from api.services.spec_generator import SpecGeneratorService
from sqlalchemy.orm import Session


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to catch and log all unhandled exceptions"""
    logging.error(
        f"Unhandled exception on {request.method} {request.url.path}:\n"
        f"Exception type: {type(exc).__name__}\n"
        f"Exception message: {str(exc)}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )
    
    # Return a generic error response (don't expose internal details)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__
        }
    )


# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(verification.router)
app.include_router(deconstruct.router)
app.include_router(projects.router)
app.include_router(github_webhooks.router)
app.include_router(github_installations.router)  # GitHub Installations API
app.include_router(blueprints.router)  # Blueprint Genesis API


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
    service = SpecGeneratorService(db, current_user)
    return service.generate_spec(request, api_key)


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
    service = SpecGeneratorService(db, current_user)
    return service.find_gaps(request)


@app.post("/api/generate/refine-spec", response_model=RefineSpecResponse)
async def refine_spec(
    request: RefineSpecRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Refine a specification by applying gap suggestions.
    Uses Gemini to generate refined spec text with selected gap suggestions applied.
    """
    service = SpecGeneratorService(db, current_user)
    return service.refine_spec(request)


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
