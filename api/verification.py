"""
Verification endpoint for Dafny code
Wraps Dafny CLI and parses verification results
"""

from fastapi import APIRouter, HTTPException
import subprocess
import tempfile
import os
import re
from typing import List, Optional, Literal, cast
import time

from api.models import (
    VerifyRequest,
    VerifyResponse,
    VerificationResult,
    VerificationError,
    GapLocation
)

router = APIRouter(prefix="/api", tags=["verification"])


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
    
    Runs Dafny CLI with the provided code and returns:
    - Verification status
    - Detailed results per method/function
    - Errors with locations
    - Proof obligations
    - Solver output
    """
    # Check if Dafny is available
    import shutil
    if not shutil.which("dafny"):
        raise HTTPException(
            status_code=503,
            detail="Dafny verifier not available. Please install Dafny CLI."
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
            f"--solver:{request.solver}",
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
