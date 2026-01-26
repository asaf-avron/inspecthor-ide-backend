"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel
from typing import List, Literal, Optional


# === Stage 1-2: Generation Models ===
class GapLocation(BaseModel):
    line: Optional[int] = None
    column: Optional[int] = None
    file: Optional[str] = None


class Gap(BaseModel):
    id: str
    severity: Literal["critical", "high", "medium", "low"]
    category: Literal["missing-precondition", "ambiguous-requirement", "incomplete-spec", "other"]
    description: str
    location: GapLocation
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None


class Ambiguity(BaseModel):
    id: str
    text: str
    possible_interpretations: List[str]
    recommendation: str


class TraceabilityEntry(BaseModel):
    id: str
    source_text: str
    code_line: str
    line_number: Optional[int] = None
    status: Literal["mapped", "partial", "missing"]
    confidence: float = 1.0


class SpecStatistics(BaseModel):
    total_requirements: int
    mapped_requirements: int
    coverage_percentage: float
    total_gaps: int
    critical_gaps: int


class GenerateSpecOptions(BaseModel):
    include_examples: bool = False
    strictness_level: Literal["low", "medium", "high"] = "medium"
    target_language: str = "dafny"


class GenerateSpecRequest(BaseModel):
    english_spec: str
    options: Optional[GenerateSpecOptions] = None


class GenerateSpecResponse(BaseModel):
    triage: dict  # { doc_type, confidence, detected_patterns }
    structured_spec: str
    dafny_skeleton: str
    gaps: List[Gap]
    ambiguities: List[Ambiguity]
    traceability_matrix: List[TraceabilityEntry]
    statistics: SpecStatistics


# === Stage 3: Verification Models ===
class ProofObligation(BaseModel):
    id: str
    name: str
    location: str
    status: Literal["verified", "failed", "pending", "warning"]
    time: Optional[str] = None
    details: Optional[str] = None


class LogEntry(BaseModel):
    time: str
    level: Literal["info", "debug", "success", "error", "warn"]
    message: str


class VerifyDafnyRequest(BaseModel):
    code: str
    filename: str


class VerifyDafnyResponse(BaseModel):
    success: bool
    proof_obligations: List[ProofObligation]
    logs: List[LogEntry]


# === Gap Resolution Models ===
class SuggestRequest(BaseModel):
    spec: str
    gap: Gap


class SuggestResponse(BaseModel):
    rationale: str
    original_text: str
    proposed_text: str


# === AI Assistant Models ===
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatContext(BaseModel):
    code: str
    location: str
    error: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[ChatContext] = None
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    content: str
    suggestions: List[str]


# === File Management Models ===
class FileSaveRequest(BaseModel):
    filename: str
    content: str
    file_type: Literal["markdown", "dafny"]
    project_id: Optional[str] = None


class FileSaveResponse(BaseModel):
    file_id: str
    filename: str
    saved_at: str
    size_bytes: int


class FileResponse(BaseModel):
    file_id: str
    filename: str
    content: str
    file_type: str
    created_at: str
    updated_at: str
    size_bytes: int


class FileListItem(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    created_at: str
    updated_at: str


class FileListResponse(BaseModel):
    files: List[FileListItem]
    total: int


# === Verification Models (Enhanced) ===
class VerificationError(BaseModel):
    type: Literal["syntax", "type", "verification"]
    line: int
    column: int
    message: str
    suggestion: Optional[str] = None


class ProofObligationDetail(BaseModel):
    id: str
    description: str
    status: Literal["proven", "failed"]
    counterexample: Optional[str] = None


class VerificationResult(BaseModel):
    type: Literal["method", "function", "invariant"]
    name: str
    location: GapLocation
    status: Literal["verified", "failed", "timeout"]
    message: str
    proof_obligations: List[ProofObligationDetail]


class VerifyRequest(BaseModel):
    dafny_code: str
    timeout_seconds: int = 30
    solver: Literal["z3", "cvc5"] = "z3"
    verbosity: Literal["quiet", "normal", "verbose"] = "normal"


class VerifyResponse(BaseModel):
    verified: bool
    verification_time_ms: int
    results: List[VerificationResult]
    errors: List[VerificationError]
    warnings: List[dict]
    solver_output: str


# === Utility Models ===
class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    dafny_available: bool
