# Guardian Gateway - Core Workflow
# State machine for the 4-stage specification workflow
# Functional Core: No Streamlit imports allowed

"""
The Workflow Engine: Manages the Triage -> Structure -> Audit -> Approve pipeline.
Implements the Product Workflow specification from Dev_Spec_Product_Flow.md.
"""

import os
import json
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# =============================================================================
# Enums
# =============================================================================

class DocType(Enum):
    """Classification of input document type."""
    SPEC = "spec"
    CODE = "code"
    JUNK = "junk"


class RigorLevel(Enum):
    """
    Rigor level for audit strictness.
    Each level has an associated risk threshold.
    """
    SANITY = "sanity"      # Threshold: 50 - Most lenient
    STANDARD = "standard"  # Threshold: 20 - Default
    PARANOID = "paranoid"  # Threshold: 0  - Most strict


class WorkflowStatus(Enum):
    """Current status in the workflow state machine."""
    DRAFT = "draft"          # Initial state, awaiting input
    ANALYZING = "analyzing"  # Processing in progress
    READY = "ready"          # Audit complete, awaiting approval
    FINALIZED = "finalized"  # Locked and immutable


# =============================================================================
# Risk Thresholds
# =============================================================================

RISK_THRESHOLDS = {
    RigorLevel.SANITY: 50,
    RigorLevel.STANDARD: 20,
    RigorLevel.PARANOID: 0,
}


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class TriageResult:
    """Result of the triage classification."""
    doc_type: DocType
    confidence: float = 0.0
    error: Optional[str] = None


@dataclass
class StructureResult:
    """Result of the structuring/normalization step."""
    structured_spec: str = ""
    validation_passed: bool = False
    error: Optional[str] = None


@dataclass
class RiskAssessment:
    """Risk calculation result."""
    score: int
    threshold: int
    is_acceptable: bool
    critical_count: int
    warning_count: int


# =============================================================================
# Prompts
# =============================================================================

TRIAGE_PROMPT = """You are a document classifier. Analyze the following text and classify it into EXACTLY one category.

Categories:
- "spec": A functional specification, requirements document, or system description
- "code": Source code, script, or programming language syntax
- "junk": Gibberish, random text, unrelated content, or empty/meaningless input

You MUST return ONLY valid JSON with this exact schema (no markdown, no explanation):
{
  "doc_type": "spec" | "code" | "junk",
  "confidence": 0.0 to 1.0
}

Rules:
- If the text describes system behavior, requirements, or features -> "spec"
- If the text contains code syntax (functions, classes, imports, etc.) -> "code"
- If the text is meaningless, random, or unrelated to software -> "junk"
- Empty or very short (<10 words) unclear text should be "junk"
"""

STRUCTURE_PROMPT = """You are a specification formatter. Rewrite the following specification into the Guardian Standard Template format.

## GUARDIAN STANDARD TEMPLATE:
The output MUST contain these sections:

### Entities
List all data entities/objects in the system with their properties.

### Invariants
List all system-wide rules that must always be true.

### Function: [FunctionName]
For each operation/feature, include:
- **Description:** What it does
- **Preconditions:** What must be true before execution
- **Postconditions:** What must be true after execution

## RULES:
- Preserve ALL original requirements and intent
- Add structure without changing meaning
- Use clear, formal language
- If information is missing, note it as "[UNSPECIFIED]"
- Output ONLY the formatted specification in Markdown (no JSON, no explanation)

## INPUT SPECIFICATION:
"""

# =============================================================================
# Workflow Manager Class
# =============================================================================

class WorkflowManager:
    """
    Manages the state machine for the Guardian specification workflow.
    
    Handles transitions between stages:
    1. Triage: Classify input as Spec/Code/Junk
    2. Structure: Normalize to Standard Template
    3. Audit: Analyze with traceability (delegated to SpecAuditor)
    4. Approve: Finalize with risk assessment
    """
    
    FLASH_MODEL = "models/gemini-1.5-flash-001"
    PRO_MODEL = "models/gemini-1.5-flash-001"  # Using flash for both since pro is not available
    FALLBACK_MODEL = "models/gemini-1.5-flash-001"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the workflow manager with an API key.
        
        Args:
            api_key: Google Gemini API key. If not provided, reads from 
                     GEMINI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._flash_model = self.FLASH_MODEL
        self._pro_model = self.PRO_MODEL
        self._init_error: Optional[str] = None
        
        if genai is None:
            self._init_error = "google-genai package not installed. Run: pip install google-genai"
        elif not self.api_key:
            self._init_error = "GEMINI_API_KEY not found. Set it in .env file or environment."
        else:
            self._init_error = None
            self._configure_genai()
    
    def _configure_genai(self) -> None:
        """Configure the Gemini API with the provided key."""
        if genai and self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self._init_error = f"Failed to initialize client: {e}"
    
    def is_configured(self) -> bool:
        """Check if the workflow manager is properly configured."""
        return self._init_error is None and hasattr(self, '_client')
    
    def get_configuration_error(self) -> Optional[str]:
        """Get the configuration error message if any."""
        return self._init_error


# =============================================================================
# Triage Function
# =============================================================================

def run_triage(text: str, api_key: Optional[str] = None) -> TriageResult:
    """
    Stage 1: Classify input text as Spec, Code, or Junk.
    
    Uses Gemini Flash with a 5-second conceptual timeout goal.
    
    Args:
        text: The raw input text to classify.
        api_key: Optional API key (uses environment if not provided).
        
    Returns:
        TriageResult with classification and confidence.
    """
    if not text or not text.strip():
        return TriageResult(doc_type=DocType.JUNK, error="Input text is empty.")
    
    # Initialize workflow manager for API access
    manager = WorkflowManager(api_key=api_key)
    if not manager.is_configured():
        return TriageResult(
            doc_type=DocType.JUNK,
            error=manager.get_configuration_error()
        )
    
    prompt = f"{TRIAGE_PROMPT}\n\n---\nTEXT TO CLASSIFY:\n---\n{text[:2000]}"  # Limit input size
    
    try:
        response = manager._client.models.generate_content(
            model=manager._flash_model,
            contents=prompt
        )
        raw_text = response.text or ""
        
        # Parse JSON response
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        data = json.loads(cleaned)
        
        doc_type_str = data.get("doc_type", "junk").lower()
        confidence = float(data.get("confidence", 0.5))
        
        # Map to enum
        if doc_type_str == "spec":
            doc_type = DocType.SPEC
        elif doc_type_str == "code":
            doc_type = DocType.CODE
        else:
            doc_type = DocType.JUNK
        
        return TriageResult(doc_type=doc_type, confidence=confidence)
        
    except json.JSONDecodeError:
        # Default to junk on parse error
        return TriageResult(
            doc_type=DocType.JUNK,
            error="Failed to parse classification response."
        )
    except Exception as e:
        return TriageResult(
            doc_type=DocType.JUNK,
            error=f"Classification failed: {str(e)}"
        )


# =============================================================================
# Structuring Function
# =============================================================================

def run_structuring(text: str, api_key: Optional[str] = None) -> StructureResult:
    """
    Stage 2: Normalize specification to Guardian Standard Template.
    
    Uses Gemini Pro for higher quality output with 15-second conceptual timeout goal.
    
    Args:
        text: The raw specification text to normalize.
        api_key: Optional API key (uses environment if not provided).
        
    Returns:
        StructureResult with normalized specification.
    """
    if not text or not text.strip():
        return StructureResult(error="Input text is empty.")
    
    # Initialize workflow manager for API access
    manager = WorkflowManager(api_key=api_key)
    if not manager.is_configured():
        return StructureResult(error=manager.get_configuration_error())
    
    prompt = f"{STRUCTURE_PROMPT}\n{text}"
    
    try:
        response = manager._client.models.generate_content(
            model=manager._pro_model,
            contents=prompt
        )
        structured_spec = (response.text or "").strip()
        
        # Validate structure - check for required sections
        validation_passed = _validate_structure(structured_spec)
        
        return StructureResult(
            structured_spec=structured_spec,
            validation_passed=validation_passed
        )
        
    except Exception as e:
        return StructureResult(error=f"Structuring failed: {str(e)}")


def _validate_structure(spec: str) -> bool:
    """
    Validate that the structured spec contains required sections.
    
    Args:
        spec: The structured specification text.
        
    Returns:
        True if validation passes, False otherwise.
    """
    spec_lower = spec.lower()
    
    # Check for required markers (case-insensitive)
    has_entities = "entities" in spec_lower or "**entities" in spec_lower
    has_function = "function:" in spec_lower or "### function" in spec_lower
    
    return has_entities and has_function


# =============================================================================
# Risk Calculation
# =============================================================================

def calculate_risk(critical_count: int, warning_count: int) -> int:
    """
    Calculate the saturated risk score.
    
    Formula: R = (10 * critical_count) + warning_count
    
    Args:
        critical_count: Number of critical gaps found.
        warning_count: Number of warning gaps found.
        
    Returns:
        Risk score as an integer.
    """
    return (10 * critical_count) + warning_count


def assess_risk(
    critical_count: int, 
    warning_count: int, 
    rigor_level: RigorLevel
) -> RiskAssessment:
    """
    Assess risk against the rigor level threshold.
    
    Args:
        critical_count: Number of critical gaps.
        warning_count: Number of warning gaps.
        rigor_level: The selected rigor level.
        
    Returns:
        RiskAssessment with score, threshold, and acceptability.
    """
    score = calculate_risk(critical_count, warning_count)
    threshold = RISK_THRESHOLDS[rigor_level]
    is_acceptable = score <= threshold
    
    return RiskAssessment(
        score=score,
        threshold=threshold,
        is_acceptable=is_acceptable,
        critical_count=critical_count,
        warning_count=warning_count
    )


def get_risk_status(assessment: RiskAssessment) -> Tuple[str, str]:
    """
    Get human-readable risk status.
    
    Args:
        assessment: The risk assessment result.
        
    Returns:
        Tuple of (status_emoji, status_text).
    """
    if assessment.is_acceptable:
        return ("✅", "Ready for Approval")
    else:
        return ("⚠️", "Review Needed")


# =============================================================================
# Auto-Refine Stub (Future Implementation)
# =============================================================================

def auto_refine_spec(spec: str, gaps: list) -> str:
    """
    Placeholder for the SpecRefiner autonomous agent.
    
    This will implement the self-healing loop from Dev_Spec_Auto_Sepc_Refinement.md.
    
    Args:
        spec: The current specification text.
        gaps: List of gaps to address.
        
    Returns:
        Refined specification text.
        
    Raises:
        NotImplementedError: Always, as this is a placeholder.
    """
    raise NotImplementedError(
        "SpecRefiner autonomous agent not yet implemented. "
        "See Dev_Spec_Auto_Sepc_Refinement.md for specification."
    )


# =============================================================================
# Test Harness
# =============================================================================

if __name__ == "__main__":
    # Simple test harness
    print("Testing Workflow Manager...")
    
    manager = WorkflowManager()
    
    if not manager.is_configured():
        print(f"Configuration Error: {manager.get_configuration_error()}")
    else:
        print("Workflow Manager configured successfully!")
        
        # Test triage
        test_spec = """
        The Rewards System allows users to earn points for completing tasks.
        Users can redeem points for rewards. Premium users get 2x points.
        """
        
        test_code = """
        def hello():
            print("Hello, world!")
        """
        
        test_junk = "asdfghjkl qwerty random nonsense 12345"
        
        print("\n--- Triage Tests ---")
        
        result1 = run_triage(test_spec)
        print(f"Spec test: {result1.doc_type.value} (confidence: {result1.confidence:.2f})")
        
        result2 = run_triage(test_code)
        print(f"Code test: {result2.doc_type.value} (confidence: {result2.confidence:.2f})")
        
        result3 = run_triage(test_junk)
        print(f"Junk test: {result3.doc_type.value} (confidence: {result3.confidence:.2f})")
        
        # Test risk calculation
        print("\n--- Risk Calculation Tests ---")
        
        assessment = assess_risk(2, 5, RigorLevel.STANDARD)
        status_emoji, status_text = get_risk_status(assessment)
        print(f"Risk Score: {assessment.score} (threshold: {assessment.threshold})")
        print(f"Status: {status_emoji} {status_text}")
