"""
Dafny Verification Service - FastAPI Application

A minimal, stateless verification service that:
- Has NO external network access
- Has NO database connections
- Has NO credentials or secrets
- Accepts Dafny code and returns verification results

This service is designed to be run in an isolated container
with no access to the outside world.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

from .models import (
    VerifyRequest,
    VerifyResponse,
    HealthResponse,
)
from .runner import (
    run_verification,
    is_dafny_available,
    is_z3_available,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Dafny Verification Service",
    description="Stateless formal verification using Dafny and Z3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Minimal CORS - only allow internal Docker network
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Will be restricted by network isolation
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns status of Dafny and Z3 availability.
    """
    dafny_available, version = is_dafny_available()
    z3_available = is_z3_available()
    
    status = "healthy" if dafny_available and z3_available else "unhealthy"
    
    return HealthResponse(
        status=status,
        dafny_available=dafny_available,
        z3_available=z3_available,
        version=version,
    )


@app.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest) -> VerifyResponse:
    """
    Verify Dafny code.
    
    Accepts either:
    - `dafny_code`: Combined specification and implementation
    - `spec_dafny` + `impl_dafny`: Separate spec and implementation
    
    Returns detailed verification results including:
    - Overall verification status
    - Per-method/function results
    - Errors with line numbers and suggestions
    - Warnings
    - Raw solver output for debugging
    """
    # Get combined code
    dafny_code = request.get_combined_code()
    
    if not dafny_code or not dafny_code.strip():
        raise HTTPException(
            status_code=400,
            detail="No Dafny code provided. Supply either 'dafny_code' or 'spec_dafny'/'impl_dafny'."
        )
    
    logger.info(
        f"Starting verification: {len(dafny_code)} chars, "
        f"timeout={request.timeout_seconds}s, solver={request.solver}"
    )
    
    try:
        verified, results, errors, warnings, time_ms, raw_output = run_verification(
            dafny_code=dafny_code,
            timeout_seconds=request.timeout_seconds,
            solver=request.solver,
            resource_limit=request.resource_limit,
        )
        
        logger.info(
            f"Verification complete: verified={verified}, "
            f"results={len(results)}, errors={len(errors)}, time={time_ms}ms"
        )
        
        return VerifyResponse(
            verified=verified,
            verification_time_ms=time_ms,
            results=results,
            errors=errors,
            warnings=warnings,
            solver_output=raw_output,
        )
        
    except RuntimeError as e:
        logger.error(f"Verification runtime error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
    except TimeoutError as e:
        logger.warning(f"Verification timeout: {e}")
        raise HTTPException(
            status_code=408,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Unexpected verification error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint - basic info."""
    return {
        "service": "Dafny Verification Service",
        "version": "1.0.0",
        "endpoints": {
            "/health": "Health check",
            "/verify": "Verify Dafny code (POST)",
            "/docs": "API documentation",
        }
    }


# Entry point for running directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
