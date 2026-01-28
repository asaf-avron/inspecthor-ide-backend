"""
Python wrapper for Docker-based Dafny verification execution.
Provides structured interface for running Dafny verification from Python code.
"""

import subprocess
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class DafnyVerificationResult:
    """Structured result from Dafny verification."""
    
    def __init__(
        self,
        success: bool,
        output: str,
        error: Optional[str] = None,
        verified_files: Optional[List[str]] = None,
        failed_files: Optional[List[str]] = None
    ):
        self.success = success
        self.output = output
        self.error = error
        self.verified_files = verified_files or []
        self.failed_files = failed_files or []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "verified_files": self.verified_files,
            "failed_files": self.failed_files
        }


def verify_dafny_files(
    files: List[str],
    docker_service: str = "api",
    timeout: int = 300
) -> DafnyVerificationResult:
    """
    Verify Dafny files using Docker container.
    
    Args:
        files: List of Dafny file paths to verify
        docker_service: Docker Compose service name (default: "api")
        timeout: Timeout in seconds (default: 300)
    
    Returns:
        DafnyVerificationResult with verification status and output
    """
    if not files:
        return DafnyVerificationResult(
            success=False,
            output="",
            error="No files provided for verification"
        )
    
    # Build docker-compose command
    cmd = [
        "docker-compose",
        "exec",
        "-T",
        docker_service,
        "dafny",
        "verify"
    ] + files
    
    logger.info(f"Running Dafny verification: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # Don't raise on non-zero exit
        )
        
        # Parse output to determine success
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        # Simple parsing: look for verification success indicators
        verified_files = []
        failed_files = []
        
        if success:
            # Extract verified files from output
            for file_path in files:
                if "verified" in output.lower() or "Dafny program verifier finished" in output:
                    verified_files.append(file_path)
        else:
            # Extract failed files from error output
            for file_path in files:
                if file_path in output:
                    failed_files.append(file_path)
        
        return DafnyVerificationResult(
            success=success,
            output=output,
            error=result.stderr if not success else None,
            verified_files=verified_files,
            failed_files=failed_files
        )
    
    except subprocess.TimeoutExpired:
        return DafnyVerificationResult(
            success=False,
            output="",
            error=f"Verification timed out after {timeout} seconds"
        )
    except Exception as e:
        return DafnyVerificationResult(
            success=False,
            output="",
            error=f"Error running Dafny verification: {str(e)}"
        )


def verify_all_dafny_specs(
    verification_dir: str = "api/verification",
    docker_service: str = "api"
) -> DafnyVerificationResult:
    """
    Verify all Dafny specification files in the verification directory.
    
    Args:
        verification_dir: Directory containing Dafny files
        docker_service: Docker Compose service name
    
    Returns:
        DafnyVerificationResult for all files
    """
    verification_path = Path(verification_dir)
    
    if not verification_path.exists():
        return DafnyVerificationResult(
            success=False,
            output="",
            error=f"Verification directory not found: {verification_dir}"
        )
    
    # Find all .dfy files
    dafny_files = list(verification_path.glob("*.dfy"))
    
    if not dafny_files:
        return DafnyVerificationResult(
            success=False,
            output="",
            error=f"No Dafny files found in {verification_dir}"
        )
    
    file_paths = [str(f) for f in dafny_files]
    logger.info(f"Found {len(file_paths)} Dafny files to verify")
    
    return verify_dafny_files(file_paths, docker_service=docker_service)
