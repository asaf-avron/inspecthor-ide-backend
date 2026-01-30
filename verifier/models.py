"""
Pydantic models for the Dafny Verification Service

These models define the strict contract between the Orchestrator
and the Verifier service.
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class VerificationError(BaseModel):
    """A single verification error from Dafny."""
    type: Literal["syntax", "type", "verification"] = "verification"
    line: int
    column: int
    message: str
    file: Optional[str] = None
    suggestion: Optional[str] = None


class ProofObligationDetail(BaseModel):
    """Details about a single proof obligation."""
    id: str
    description: str
    status: Literal["proven", "failed"]
    counterexample: Optional[str] = None


class VerificationResultItem(BaseModel):
    """Result for a single method/function/lemma verification."""
    type: Literal["method", "function", "lemma", "invariant"]
    name: str
    status: Literal["verified", "failed", "timeout"]
    message: str
    line: Optional[int] = None
    proof_obligations: List[ProofObligationDetail] = []


class VerifyRequest(BaseModel):
    """
    Request to verify Dafny code.
    
    The verifier accepts either:
    1. Combined dafny_code (spec + impl in one file)
    2. Separate spec_dafny and impl_dafny (will be concatenated)
    """
    # Option 1: Single combined code
    dafny_code: Optional[str] = Field(
        None, 
        description="Combined Dafny code (specification + implementation)"
    )
    
    # Option 2: Separate spec and implementation
    spec_dafny: Optional[str] = Field(
        None,
        description="Dafny specification code (traits, predicates, contracts)"
    )
    impl_dafny: Optional[str] = Field(
        None,
        description="Dafny implementation code that should satisfy the spec"
    )
    
    # Verification options
    timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=600,
        description="Timeout for verification in seconds"
    )
    solver: Literal["z3", "cvc5"] = Field(
        default="z3",
        description="SMT solver to use"
    )
    resource_limit: Optional[int] = Field(
        default=None,
        description="Resource limit for the solver (optional)"
    )
    
    def get_combined_code(self) -> str:
        """Get the combined Dafny code to verify."""
        if self.dafny_code:
            return self.dafny_code
        
        parts = []
        if self.spec_dafny:
            parts.append(self.spec_dafny.strip())
        if self.impl_dafny:
            parts.append(self.impl_dafny.strip())
        
        return "\n\n".join(parts)


class VerifyResponse(BaseModel):
    """Response from verification."""
    verified: bool = Field(
        description="True if all proof obligations were satisfied"
    )
    verification_time_ms: int = Field(
        description="Time taken for verification in milliseconds"
    )
    results: List[VerificationResultItem] = Field(
        default=[],
        description="Per-method/function verification results"
    )
    errors: List[VerificationError] = Field(
        default=[],
        description="Verification errors with locations"
    )
    warnings: List[str] = Field(
        default=[],
        description="Non-fatal warnings from Dafny"
    )
    solver_output: str = Field(
        default="",
        description="Raw output from Dafny for debugging"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "unhealthy"]
    dafny_available: bool
    z3_available: bool
    version: Optional[str] = None
