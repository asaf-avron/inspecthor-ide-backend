"""
Dafny verification runner

Pure functions for executing Dafny verification and parsing results.
No side effects except filesystem (temp files) and subprocess execution.
"""

import subprocess
import tempfile
import os
import re
import time
import shutil
from typing import List, Tuple, Optional

from .models import (
    VerificationError,
    VerificationResultItem,
)


def is_dafny_available() -> Tuple[bool, Optional[str]]:
    """
    Check if Dafny CLI is available.
    
    Returns:
        (available, version_string)
    """
    if not shutil.which("dafny"):
        return False, None
    
    try:
        result = subprocess.run(
            ["dafny", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        version = result.stdout.strip() if result.returncode == 0 else None
        return True, version
    except Exception:
        return False, None


def is_z3_available() -> bool:
    """Check if Z3 solver is available."""
    # Check common paths for Z3
    z3_paths = [
        shutil.which("z3"),
        shutil.which("z3-4.12.1"),
        "/root/.dotnet/tools/z3/bin/z3-4.12.1",
    ]
    return any(path and os.path.exists(path) for path in z3_paths if path)


def generate_suggestion(error_message: str) -> Optional[str]:
    """Generate helpful suggestions based on error message."""
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
    elif "type" in error_lower or "expected" in error_lower:
        return "Check type compatibility between expected and actual types"
    
    return None


def parse_dafny_output(
    output: str, 
    return_code: int
) -> Tuple[bool, List[VerificationResultItem], List[VerificationError], List[str]]:
    """
    Parse Dafny verification output into structured results.
    
    Args:
        output: Combined stdout + stderr from Dafny
        return_code: Process return code
    
    Returns:
        (verified, results, errors, warnings)
    """
    results: List[VerificationResultItem] = []
    errors: List[VerificationError] = []
    warnings: List[str] = []
    
    # Check if verification succeeded
    # Dafny outputs "Dafny program verifier finished with X verified, 0 errors"
    verified = return_code == 0 and "0 errors" in output
    
    # Also check for explicit success message
    if "Dafny program verifier finished" in output and "0 errors" in output:
        verified = True
    
    # Extract method/function/lemma verification status
    # Pattern matches lines like "Verifying module_name.MethodName ..."
    method_pattern = r'(?:Verifying\s+)?(?:\w+\.)?(\w+)\s+\((?:method|function|lemma)\).*?(verified|error|timed out)'
    for match in re.finditer(method_pattern, output, re.IGNORECASE):
        method_name = match.group(1)
        status_text = match.group(2).lower()
        
        if "verified" in status_text:
            status = "verified"
        elif "timed out" in status_text:
            status = "timeout"
        else:
            status = "failed"
        
        results.append(VerificationResultItem(
            type="method",
            name=method_name,
            status=status,  # type: ignore
            message=f"{method_name} {status}"
        ))
    
    # Also try simpler pattern for Dafny 4.x output
    simple_pattern = r'(method|function|lemma)\s+(\w+).*?(verified|error)'
    for match in re.finditer(simple_pattern, output, re.IGNORECASE):
        method_type = match.group(1).lower()
        method_name = match.group(2)
        status_text = match.group(3).lower()
        
        # Skip if already found
        if any(r.name == method_name for r in results):
            continue
        
        status = "verified" if "verified" in status_text else "failed"
        
        # Map lemma to method for compatibility
        result_type = method_type if method_type in ["method", "function"] else "method"
        
        results.append(VerificationResultItem(
            type=result_type,  # type: ignore
            name=method_name,
            status=status,  # type: ignore
            message=f"{method_type.capitalize()} {method_name} {status}"
        ))
    
    # Parse errors
    # Pattern: "file.dfy(10,5): Error: assertion violation"
    # Also handles: "file.dfy(10,5): Error BP5001: assertion violation"
    error_pattern = r'(\S+\.dfy)\((\d+),(\d+)\):\s*Error(?:\s+\w+)?:\s*(.+?)(?=\n|$)'
    for match in re.finditer(error_pattern, output):
        file_name = match.group(1)
        line = int(match.group(2))
        column = int(match.group(3))
        message = match.group(4).strip()
        
        errors.append(VerificationError(
            type="verification",
            line=line,
            column=column,
            message=message,
            file=file_name,
            suggestion=generate_suggestion(message)
        ))
    
    # Parse warnings
    warning_pattern = r'Warning(?:\s+\w+)?:\s*(.+?)(?=\n|$)'
    for match in re.finditer(warning_pattern, output):
        warnings.append(match.group(1).strip())
    
    # If no results parsed but we have a summary, extract from summary
    summary_pattern = r'Dafny program verifier finished with (\d+) verified, (\d+) error'
    summary_match = re.search(summary_pattern, output)
    if summary_match and not results:
        verified_count = int(summary_match.group(1))
        error_count = int(summary_match.group(2))
        verified = error_count == 0 and verified_count > 0
    
    return verified, results, errors, warnings


def run_verification(
    dafny_code: str,
    timeout_seconds: int = 60,
    solver: str = "z3",
    resource_limit: Optional[int] = None,
) -> Tuple[bool, List[VerificationResultItem], List[VerificationError], List[str], int, str]:
    """
    Run Dafny verification on the provided code.
    
    Args:
        dafny_code: The Dafny code to verify
        timeout_seconds: Timeout for verification
        solver: SMT solver to use (z3 or cvc5)
        resource_limit: Optional resource limit for solver
    
    Returns:
        (verified, results, errors, warnings, time_ms, raw_output)
    
    Raises:
        RuntimeError: If Dafny is not available
        TimeoutError: If verification times out
    """
    dafny_available, _ = is_dafny_available()
    if not dafny_available:
        raise RuntimeError("Dafny verifier not available")
    
    # Create temporary file for Dafny code
    with tempfile.NamedTemporaryFile(
        mode='w', 
        suffix='.dfy', 
        delete=False,
        encoding='utf-8'
    ) as f:
        f.write(dafny_code)
        temp_file = f.name
    
    try:
        # Build Dafny command
        cmd = [
            "dafny",
            "verify",
            temp_file,
            f"--verification-time-limit:{timeout_seconds}",
        ]
        
        # Add solver configuration
        if solver == "z3":
            # Check for Z3 in known locations
            z3_path = "/root/.dotnet/tools/z3/bin/z3-4.12.1"
            if os.path.exists(z3_path):
                cmd.append(f"--solver-path:{z3_path}")
        
        # Add resource limit if specified
        if resource_limit:
            cmd.append(f"--resource-limit:{resource_limit}")
        
        # Allow warnings (don't fail on warnings)
        cmd.append("--allow-warnings")
        
        # Run Dafny verification
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 10  # Add buffer for process overhead
        )
        verification_time_ms = int((time.time() - start_time) * 1000)
        
        # Combine output
        raw_output = result.stdout + result.stderr
        
        # Parse output
        verified, results, errors, warnings = parse_dafny_output(
            raw_output, 
            result.returncode
        )
        
        return verified, results, errors, warnings, verification_time_ms, raw_output
        
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Verification timed out after {timeout_seconds} seconds")
    
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.unlink(temp_file)
