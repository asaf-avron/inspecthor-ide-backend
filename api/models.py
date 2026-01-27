"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel
from typing import List, Literal, Optional
from datetime import datetime


# === Stage 1-2: Generation Models ===
class GenerateSpecRequest(BaseModel):
    english_spec: str
    rigor_level: Literal["sanity", "standard", "paranoid"] = "standard"


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
    file_type: Literal["md", "dfy", "unit"]
    project_id: str  # Required - files must belong to a project


class FileSaveResponse(BaseModel):
    file_id: str
    filename: str
    saved_at: str
    size_bytes: int


class FileUpdateRequest(BaseModel):
    content: str
    filename: Optional[str] = None  # Optional rename


class FileResponse(BaseModel):
    file_id: str
    filename: str
    content: str
    file_type: str
    project_id: str
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


# === Project Management Models ===
class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str
    file_count: int
    redirect_url: Optional[str] = None


class ProjectListRequest(BaseModel):
    limit: int = 100
    offset: int = 0
    sort: Literal["created_at", "updated_at", "name"] = "updated_at"
    order: Literal["asc", "desc"] = "desc"


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
    limit: int
    offset: int


class FileMetadata(BaseModel):
    file_id: str
    filename: str
    file_type: str
    updated_at: str
    size_bytes: int


class ProjectStructureResponse(BaseModel):
    project: ProjectResponse
    files: List[FileMetadata]


class ProjectDeleteResponse(BaseModel):
    deleted: bool
    project_id: str
    files_deleted: int


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


# === Deconstruction Models ===
class UnitCandidate(BaseModel):
    title: str
    description: str
    requirements: List[str]
    line_range: List[int]  # [start_line, end_line]
    dependencies: List[str] = []


class UnitInfo(BaseModel):
    unit_id: str
    unit_filename: str
    dafny_filename: str
    title: str
    description: str
    requirements: List[str]
    dafny_code: str
    line_range: List[int]  # [start_line, end_line]


class UnitLinkInfo(BaseModel):
    link_id: str
    unit_file_id: str
    dafny_file_id: str
    source_file_id: str
    link_type: str
    title: str
    source_range: dict  # {"start_line": int, "end_line": int}
    verification_status: str
    created_at: str


class DeconstructStats(BaseModel):
    total_units: int
    successful_units: int
    failed_units: int
    total_files_created: int
    processing_time_seconds: float


class DeconstructRequest(BaseModel):
    project_id: str
    source_file_id: str
    strategy: Literal["auto", "manual"] = "auto"
    max_units: Optional[int] = None
    unit_boundaries: Optional[List[List[int]]] = None  # [[start, end], ...]


class DeconstructResponse(BaseModel):
    units: List[UnitInfo]
    links: List[UnitLinkInfo]
    statistics: DeconstructStats
    errors: List[str]


class TraceabilityLink(BaseModel):
    unit_id: str
    dafny_file_id: str
    title: str
    source_range: dict  # {"start_line": int, "end_line": int}
    status: str


class TraceabilityResponse(BaseModel):
    source_file_id: str
    links: List[TraceabilityLink]


# === Authentication Models ===
class GitHubAuthResponse(BaseModel):
    authorization_url: str


class UserResponse(BaseModel):
    user_id: str
    github_id: int
    github_login: str
    email: Optional[str]
    avatar_url: Optional[str]
    tier: str
    verification_credits: int
    created_at: datetime
    last_login_at: Optional[datetime]


class TokenRefreshResponse(BaseModel):
    access_token: str
    expires_in: int
