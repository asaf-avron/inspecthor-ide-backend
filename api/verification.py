"""
Verification endpoint for Dafny code

This module provides the /api/verify endpoint that delegates verification
to the isolated Verifier Service. For local development without Docker,
it falls back to direct Dafny CLI execution.
"""

from fastapi import APIRouter, HTTPException
import subprocess
import tempfile
import os
import re
from typing import List, Optional, Literal, cast
import time
import logging

from api.models import (
    VerifyRequest,
    VerifyResponse,
    VerifyPythonRequest,
    VerificationResult,
    VerificationError,
    GapLocation
)
from api.services.verifier_client import VerifierClient, is_verifier_available
from api.guardian import check_python_source
from api.transpiler import transpile_python_to_dafny
from api.transpiler.merger import DafnyMerger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["verification"])

# Configuration
USE_VERIFIER_SERVICE = os.getenv("USE_VERIFIER_SERVICE", "true").lower() == "true"


def parse_dafny_output(output: str, return_code: int) -> tuple[bool, List[VerificationResult], List[VerificationError]]:
    """
    Parse Dafny verification output into structured results.
    
    Returns:
        (verified, results, errors)
    """
    results = []
    errors = []
    
    # Check if verification succeeded
    verified = return_code == 0 and "0 errors" in output
    
    # Parse verification results
    # Example Dafny output patterns:
    # "Dafny program verifier finished with 2 verified, 0 errors"
    # "method Foo verified"
    
    # Extract method/function verification status
    method_pattern = r'(method|function|lemma)\s+(\w+).*?(verified|error)'
    for match in re.finditer(method_pattern, output, re.IGNORECASE):
        method_type = match.group(1)
        method_name = match.group(2)
        status = "verified" if "verified" in match.group(3).lower() else "failed"
        
        # Cast to Literal types for VerificationResult
        result_type: Literal["method", "function", "invariant"] = cast(
            Literal["method", "function", "invariant"],
            method_type if method_type in ["method", "function"] else "method"
        )
        result_status: Literal["verified", "failed", "timeout"] = cast(
            Literal["verified", "failed", "timeout"],
            "verified" if status == "verified" else "failed"
        )
        
        results.append(VerificationResult(
            type=result_type,
            name=method_name,
            location=GapLocation(line=None, column=None, file=None),
            status=result_status,
            message=f"{method_type.capitalize()} {method_name} {status}",
            proof_obligations=[]
        ))
    
    # Parse errors
    # Example: "file.dfy(10,5): Error: assertion violation"
    error_pattern = r'(\w+\.dfy)\((\d+),(\d+)\):\s*(Error|Warning):\s*(.+)'
    for match in re.finditer(error_pattern, output):
        file_name = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3))
        error_type = match.group(4).lower()
        message = match.group(5).strip()
        
        if error_type == "error":
            errors.append(VerificationError(
                type="verification",
                line=line,
                column=column,
                message=message,
                suggestion=generate_suggestion(message)
            ))
    
    return verified, results, errors


def generate_suggestion(error_message: str) -> Optional[str]:
    """Generate helpful suggestions based on error message"""
    error_lower = error_message.lower()
    
    if "assertion" in error_lower:
        return "Try adding a stronger precondition or loop invariant"
    elif "postcondition" in error_lower:
        return "Check if all execution paths satisfy the postcondition"
    elif "precondition" in error_lower:
        return "Ensure the precondition is met before calling this method"
    elif "invariant" in error_lower:
        return "Strengthen the loop invariant to maintain the property"
    elif "decreases" in error_lower:
        return "Add or fix the decreases clause for termination proof"
    
    return None


@router.post("/verify", response_model=VerifyResponse)
async def verify_dafny(request: VerifyRequest):
    """
    Verify Dafny code and return detailed verification results.
    
    This endpoint delegates to the isolated Verifier Service when available.
    Falls back to local Dafny CLI for development environments.
    
    Returns:
    - Verification status
    - Detailed results per method/function
    - Errors with locations
    - Proof obligations
    - Solver output
    """
    # Try verifier service first (preferred in production)
    if USE_VERIFIER_SERVICE:
        try:
            if await is_verifier_available():
                return await verify_via_service(request)
            else:
                logger.info("Verifier service not available, falling back to local Dafny")
        except Exception as e:
            logger.warning(f"Verifier service error, falling back to local: {e}")
    
    # Fall back to local Dafny CLI
    return await verify_local(request)


@router.post("/verify/python", response_model=VerifyResponse)
async def verify_python(request: VerifyPythonRequest):
    """
    Verify Python implementation against a Dafny contract (Dual-Channel flow).

    Flow: Guardian AST gate -> deterministic Transpiler -> merge with contract -> Dafny verify.
    If the Guardian rejects the Python (dirty code), returns REJECTED_BY_ARCHITECT without
    sending code to the Transpiler or Dafny.
    Contract: provide contract_code inline, or spec_id to read from Trust Registry.
    """
    # Resolve contract: from Trust Registry if spec_id set, else inline contract_code
    contract_code: Optional[str] = None
    if request.spec_id:
        from api.trust_registry import get_trust_registry
        contract_code = get_trust_registry().get_contract(request.spec_id)
        if not contract_code:
            return VerifyResponse(
                verified=False,
                verification_time_ms=0,
                results=[],
                errors=[VerificationError(
                    type="verification",
                    line=0,
                    column=0,
                    message=f"Spec not found in Trust Registry: {request.spec_id}",
                    suggestion=None,
                )],
                warnings=[],
                solver_output="",
                guardian_status="OK",
            )
    else:
        contract_code = request.contract_code
    if not contract_code:
        return VerifyResponse(
            verified=False,
            verification_time_ms=0,
            results=[],
            errors=[VerificationError(
                type="verification",
                line=0,
                column=0,
                message="Either contract_code or spec_id must be provided",
                suggestion=None,
            )],
            warnings=[],
            solver_output="",
            guardian_status="OK",
        )

    # 1. Guardian AST gate
    guardian_result = check_python_source(request.python_code)
    if not guardian_result.passed:
        return VerifyResponse(
            verified=False,
            verification_time_ms=0,
            results=[],
            errors=[],
            warnings=[],
            solver_output="",
            guardian_status="REJECTED_BY_ARCHITECT",
            guardian_reason=guardian_result.reason or "Code rejected by Guardian AST gate.",
        )

    # 2. Deterministic Transpiler (Verification Bridge)
    transpile_result = transpile_python_to_dafny(request.python_code)
    if not transpile_result.success:
        return VerifyResponse(
            verified=False,
            verification_time_ms=0,
            results=[],
            errors=[VerificationError(
                type="verification",
                line=0,
                column=0,
                message=transpile_result.error or "Transpilation failed",
                suggestion=None,
            )],
            warnings=[],
            solver_output="",
            guardian_status="OK",
        )

    # 3. Merge contract with implementation
    merger = DafnyMerger()
    merge_result = merger.merge_contract_and_impl(
        contract=contract_code,
        implementation=transpile_result.dafny_code,
    )
    if not merge_result.success:
        return VerifyResponse(
            verified=False,
            verification_time_ms=0,
            results=[],
            errors=[VerificationError(
                type="verification",
                line=0,
                column=0,
                message=merge_result.error or "Merge failed",
                suggestion=None,
            )],
            warnings=[],
            solver_output="",
            guardian_status="OK",
        )

    # 4. Verify merged Dafny (wrap in module if needed for Dafny)
    merged_code = merge_result.merged_code
    if not merged_code.strip().startswith("module "):
        merged_code = f"module M {{\n{merged_code}\n}}"
    verify_request = VerifyRequest(
        dafny_code=merged_code,
        timeout_seconds=request.timeout_seconds,
        solver=request.solver,
    )
    response = await verify_dafny(verify_request)
    return VerifyResponse(
        verified=response.verified,
        verification_time_ms=response.verification_time_ms,
        results=response.results,
        errors=response.errors,
        warnings=response.warnings,
        solver_output=response.solver_output,
        guardian_status="OK",
    )


async def verify_via_service(request: VerifyRequest) -> VerifyResponse:
    """
    Verify via the isolated Verifier Service.
    
    This is the preferred path in production - the verifier runs in
    an isolated container with no credentials.
    """
    client = VerifierClient()
    
    try:
        result = await client.verify(
            dafny_code=request.dafny_code,
            timeout_seconds=request.timeout_seconds,
            solver=request.solver,
        )
        
        # Convert verifier client result to API response format
        return VerifyResponse(
            verified=result.verified,
            verification_time_ms=result.verification_time_ms,
            results=[
                VerificationResult(
                    type=cast(Literal["method", "function", "invariant"], r.type if r.type in ["method", "function"] else "method"),
                    name=r.name,
                    location=GapLocation(line=r.line, column=None, file=None),
                    status=cast(Literal["verified", "failed", "timeout"], r.status),
                    message=r.message,
                    proof_obligations=[]
                )
                for r in result.results
            ],
            errors=[
                VerificationError(
                    type=cast(Literal["syntax", "type", "verification"], e.type),
                    line=e.line,
                    column=e.column,
                    message=e.message,
                    suggestion=e.suggestion
                )
                for e in result.errors
            ],
            warnings=[{"message": w} for w in result.warnings],
            solver_output=result.solver_output
        )
        
    except Exception as e:
        logger.error(f"Verifier service request failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Verifier service error: {str(e)}"
        )


async def verify_local(request: VerifyRequest) -> VerifyResponse:
    """
    Verify using local Dafny CLI.
    
    This is the fallback path for development environments
    where the verifier service is not running.
    """
    # Check if Dafny is available
    import shutil
    if not shutil.which("dafny"):
        raise HTTPException(
            status_code=503,
            detail="Dafny verifier not available. Please install Dafny CLI or start the verifier service."
        )
    
    # Create temporary file for Dafny code
    with tempfile.NamedTemporaryFile(mode='w', suffix='.dfy', delete=False) as f:
        f.write(request.dafny_code)
        temp_file = f.name
    
    try:
        # Build Dafny command
        cmd = [
            "dafny",
            "verify",
            temp_file,
            f"--verification-time-limit:{request.timeout_seconds}"
        ]
        
        # Add verbosity flag
        if request.verbosity == "verbose":
            cmd.append("--verbose")
        elif request.verbosity == "quiet":
            cmd.append("--quiet")
        
        # Run Dafny verification
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds + 5  # Add buffer for process overhead
        )
        verification_time_ms = int((time.time() - start_time) * 1000)
        
        # Parse output
        output = result.stdout + result.stderr
        verified, results, errors = parse_dafny_output(output, result.returncode)
        
        # Extract warnings (non-critical issues)
        warnings = []
        warning_pattern = r'Warning:\s*(.+)'
        for match in re.finditer(warning_pattern, output):
            warnings.append({"message": match.group(1).strip()})
        
        return VerifyResponse(
            verified=verified,
            verification_time_ms=verification_time_ms,
            results=results,
            errors=errors,
            warnings=warnings,
            solver_output=output
        )
        
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail=f"Verification timeout after {request.timeout_seconds} seconds"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.unlink(temp_file)
