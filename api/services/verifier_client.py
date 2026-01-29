"""
Verifier Service Client

HTTP client for calling the isolated Dafny Verification Service.
The Orchestrator uses this to request verification without exposing
any credentials to the verification engine.
"""

import os
import logging
from typing import Optional, List
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)

# Verifier service URL - defaults to Docker Compose service name
VERIFIER_URL = os.getenv("VERIFIER_URL", "http://localhost:8001")

# Timeout for verification requests (includes Dafny execution time)
VERIFIER_TIMEOUT = int(os.getenv("VERIFIER_TIMEOUT", "120"))


@dataclass
class VerificationError:
    """A single verification error."""
    type: str
    line: int
    column: int
    message: str
    file: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class VerificationResultItem:
    """Result for a single method/function."""
    type: str
    name: str
    status: str
    message: str
    line: Optional[int] = None


@dataclass
class VerifyResult:
    """Complete verification result."""
    verified: bool
    verification_time_ms: int
    results: List[VerificationResultItem]
    errors: List[VerificationError]
    warnings: List[str]
    solver_output: str
    
    @classmethod
    def from_dict(cls, data: dict) -> "VerifyResult":
        """Create from API response dict."""
        return cls(
            verified=data.get("verified", False),
            verification_time_ms=data.get("verification_time_ms", 0),
            results=[
                VerificationResultItem(
                    type=r.get("type", "method"),
                    name=r.get("name", ""),
                    status=r.get("status", "failed"),
                    message=r.get("message", ""),
                    line=r.get("line"),
                )
                for r in data.get("results", [])
            ],
            errors=[
                VerificationError(
                    type=e.get("type", "verification"),
                    line=e.get("line", 0),
                    column=e.get("column", 0),
                    message=e.get("message", ""),
                    file=e.get("file"),
                    suggestion=e.get("suggestion"),
                )
                for e in data.get("errors", [])
            ],
            warnings=data.get("warnings", []),
            solver_output=data.get("solver_output", ""),
        )


class VerifierClient:
    """
    Client for the Dafny Verification Service.
    
    This client sends verification requests to the isolated verifier service.
    The verifier has no knowledge of GitHub, databases, or any credentials.
    """
    
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[int] = None):
        self.base_url = base_url or VERIFIER_URL
        self.timeout = timeout or VERIFIER_TIMEOUT
    
    async def health_check(self) -> dict:
        """
        Check if the verifier service is healthy.
        
        Returns:
            Health status dict with dafny_available and z3_available
        """
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self.base_url}/health",
                    timeout=10
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error(f"Verifier health check failed: {e}")
                return {
                    "status": "unhealthy",
                    "dafny_available": False,
                    "z3_available": False,
                    "error": str(e),
                }
    
    async def verify(
        self,
        dafny_code: Optional[str] = None,
        spec_dafny: Optional[str] = None,
        impl_dafny: Optional[str] = None,
        timeout_seconds: int = 60,
        solver: str = "z3",
    ) -> VerifyResult:
        """
        Verify Dafny code via the verifier service.
        
        Args:
            dafny_code: Combined Dafny code (spec + impl)
            spec_dafny: Separate specification code
            impl_dafny: Separate implementation code
            timeout_seconds: Verification timeout
            solver: SMT solver to use (z3 or cvc5)
        
        Returns:
            VerifyResult with verification status and details
        
        Raises:
            httpx.HTTPStatusError: If the request fails
            httpx.TimeoutException: If verification times out
        """
        payload = {
            "timeout_seconds": timeout_seconds,
            "solver": solver,
        }
        
        if dafny_code:
            payload["dafny_code"] = dafny_code
        if spec_dafny:
            payload["spec_dafny"] = spec_dafny
        if impl_dafny:
            payload["impl_dafny"] = impl_dafny
        
        logger.info(
            f"Sending verification request: "
            f"code_len={len(dafny_code or '')} + spec_len={len(spec_dafny or '')} + impl_len={len(impl_dafny or '')}, "
            f"timeout={timeout_seconds}s"
        )
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/verify",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            
            result = VerifyResult.from_dict(resp.json())
            
            logger.info(
                f"Verification complete: verified={result.verified}, "
                f"errors={len(result.errors)}, time={result.verification_time_ms}ms"
            )
            
            return result


# Convenience functions for simple usage
async def verify_code(
    spec_dafny: str,
    impl_dafny: str,
    timeout_seconds: int = 60,
) -> VerifyResult:
    """
    Verify implementation against specification.
    
    This is the primary function for the Orchestrator to call
    when verifying code from a webhook.
    
    Args:
        spec_dafny: The formal specification (Dafny traits/contracts)
        impl_dafny: The transpiled implementation (Dafny code)
        timeout_seconds: Verification timeout
    
    Returns:
        VerifyResult with verification status
    """
    client = VerifierClient()
    return await client.verify(
        spec_dafny=spec_dafny,
        impl_dafny=impl_dafny,
        timeout_seconds=timeout_seconds,
    )


async def verify_dafny_code(
    dafny_code: str,
    timeout_seconds: int = 60,
) -> VerifyResult:
    """
    Verify combined Dafny code.
    
    Args:
        dafny_code: Complete Dafny code to verify
        timeout_seconds: Verification timeout
    
    Returns:
        VerifyResult with verification status
    """
    client = VerifierClient()
    return await client.verify(
        dafny_code=dafny_code,
        timeout_seconds=timeout_seconds,
    )


async def is_verifier_available() -> bool:
    """Check if the verifier service is available and healthy."""
    client = VerifierClient()
    health = await client.health_check()
    return health.get("status") == "healthy"
