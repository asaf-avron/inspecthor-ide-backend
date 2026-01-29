# Guardian Gateway - Core Auditor
# LLM-powered specification analysis using Google Gemini
# Functional Core: No Streamlit imports allowed

"""
The Spec Auditor: Analyzes specification text for logic gaps and ambiguities.
Uses Google Gemini to perform semantic analysis and generate Dafny skeletons.
"""

import os
import json
import re
from dataclasses import dataclass, field
from typing import Optional

# Constants for knowledge base
DEFAULT_KNOWLEDGE_PATH = "docs/knowledge/dafny_ref.md"
MAX_KNOWLEDGE_CHARS = 8000  # Truncate to prevent token overflow

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Gap:
    """Represents a single logic gap found in a specification."""
    severity: str  # "critical" or "warning"
    description: str


@dataclass
class TraceabilityEntry:
    """
    Represents a single requirement in the traceability matrix.
    Maps English requirements to Dafny code locations.
    
    Attributes:
        id: Unique identifier formatted as "REF-XX"
        source_text: The extracted English requirement sentence
        status: Traceability status (Pending, Implemented, Verified, Missing, Obsolete)
        code_line: Reference to Dafny code location (e.g., "line 42") or empty
    """
    id: str
    source_text: str
    status: str = "Pending"  # Pending | Implemented | Verified | Missing | Obsolete
    code_line: str = ""


@dataclass
class Suggestion:
    """
    Represents an AI-generated fix suggestion for a specification gap.
    
    Attributes:
        gap_id: Identifier for the gap being addressed
        original_text: The snippet of spec text that needs fixing
        proposed_text: The AI-generated replacement text
        rationale: Explanation of why this fix addresses the gap
    """
    gap_id: str
    original_text: str
    proposed_text: str
    rationale: str


@dataclass
class GapReport:
    """
    Represents the full audit report for a specification.
    
    Attributes:
        gaps: List of logic gaps (critical issues, missing validations)
        ambiguities: List of vague or unclear definitions
        dafny_skeleton: Generated Dafny trait code skeleton with // [REF-XX] comments
        tagged_spec: The spec rewritten with inline [REF-XX] tags
        traceability_matrix: List mapping requirements to code locations
        raw_response: The raw LLM response for debugging
        error: Error message if the audit failed
    """
    gaps: list[Gap] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    dafny_skeleton: str = ""
    tagged_spec: str = ""
    traceability_matrix: list[TraceabilityEntry] = field(default_factory=list)
    raw_response: str = ""
    error: Optional[str] = None


# System prompt for the LLM
SYSTEM_PROMPT = """You are a Senior Formal Verification Engineer specializing in smart contract security and formal methods.

## TRACEABILITY INSTRUCTION (CRITICAL):
Break the spec into ATOMIC REQUIREMENTS. An atomic requirement is any sentence or independent clause containing a Normative Keyword: "MUST", "SHALL", "SHOULD", "WILL", "REQUIRES", "ENSURES", or similar imperative language.

For each atomic requirement:
1. Assign a unique ID in the format [REF-XX] where XX is a sequential number starting at 01
2. Rewrite the original spec text with these [REF-XX] tags inserted inline before each requirement
3. In the Dafny skeleton, add // [REF-XX] comments on the lines that implement each requirement

## ANALYSIS TASKS:
1. **Critical Logic Gaps**: Missing validations (negative numbers, zero amounts, null checks), race conditions, missing edge cases, exploitable logic holes
2. **Ambiguities**: Vague definitions, unclear state transitions, undefined terms
3. **Missing Preconditions/Postconditions**: What should be guaranteed before and after operations

## OUTPUT FORMAT:
You MUST return ONLY valid JSON with this exact schema (no markdown, no explanation):
{
  "gaps": [
    {"severity": "critical", "description": "Description of the gap"},
    {"severity": "warning", "description": "Description of minor issue"}
  ],
  "ambiguities": [
    "First ambiguous definition or unclear requirement",
    "Second ambiguous item"
  ],
  "tagged_spec": "The FULL specification text rewritten with [REF-XX] tags inline before each atomic requirement",
  "traceability_matrix": [
    {"id": "REF-01", "source_text": "The extracted requirement text", "status": "Pending", "code_line": "ensures clause line reference"},
    {"id": "REF-02", "source_text": "Another requirement", "status": "Pending", "code_line": ""}
  ],
  "dafny_skeleton": "trait SpecName {\\n  // [REF-01] comment\\n  // Dafny code here\\n}"
}

## RULES:
- severity must be either "critical" or "warning"
- Find at least 2-3 gaps if the spec has any complexity
- tagged_spec MUST contain the full spec with [REF-XX] tags inserted
- traceability_matrix MUST list ALL atomic requirements found
- status should be "Pending" for all entries (will be updated later)
- code_line should reference the Dafny clause that implements the requirement (e.g., "ensures line 5") or empty if not yet mapped
- dafny_skeleton should include method signatures with requires/ensures clauses, each annotated with // [REF-XX] comments
- Use \\n for newlines in string fields

## CRITICAL Dafny Rules for Map Operations:
- If a method transforms a map (e.g., returns new_db from db), you MUST add a STRUCTURAL INTEGRITY clause:
  ensures success ==> (forall k :: k in db <==> k in new_db)
  This tells Dafny that keys are preserved, which is required before accessing new_db[key] in other ensures clauses.
- Always add requires clauses for map key existence BEFORE accessing map values (e.g., requires sender in db)
- Order of ensures clauses matters: structural integrity FIRST, then value-based postconditions"""


def load_knowledge_base(path: Optional[str] = None) -> Optional[str]:
    """
    Load Dafny reference documentation for RAG-enhanced analysis.
    
    Args:
        path: Path to knowledge file. Defaults to docs/knowledge/dafny_ref.md.
        
    Returns:
        File contents (possibly truncated) or None if file doesn't exist.
    """
    if path is None:
        # Resolve relative to this file's location
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, DEFAULT_KNOWLEDGE_PATH)
    
    # Graceful fallback if file doesn't exist
    if not os.path.isfile(path):
        return None
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Truncate if too large to prevent token overflow
        if len(content) > MAX_KNOWLEDGE_CHARS:
            content = content[:MAX_KNOWLEDGE_CHARS] + "\n\n[... truncated for brevity ...]"
        
        return content
        
    except IOError:
        return None


class SpecAuditor:
    """
    LLM-powered specification auditor using Google Gemini.
    
    Preconditions: GEMINI_API_KEY must be set in environment.
    Postconditions: Returns a GapReport with analysis results or error.
    """
    
    DEFAULT_MODEL = "gemini-2.0-flash-001"
    FALLBACK_MODEL = "gemini-2.0-flash-001"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the auditor with an API key.
        
        Args:
            api_key: Google Gemini API key. If not provided, reads from 
                     GEMINI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model: Optional[str] = None
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
            self._client = genai.Client(api_key=self.api_key)
            try:
                self._model = self.DEFAULT_MODEL
            except Exception as e:
                self._init_error = f"Failed to initialize client: {e}"
    
    def is_configured(self) -> bool:
        """Check if the auditor is properly configured."""
        return self._init_error is None and hasattr(self, '_client')
    
    def get_configuration_error(self) -> Optional[str]:
        """Get the configuration error message if any."""
        return self._init_error
    
    def audit_spec(self, spec_text: str) -> GapReport:
        """
        Analyze a specification text for logic gaps and ambiguities.
        
        Uses RAG-enhanced analysis by injecting Dafny reference documentation
        when available.
        
        Args:
            spec_text: The English specification text to analyze.
            
        Returns:
            GapReport containing gaps, ambiguities, and Dafny skeleton.
        """
        # Check configuration
        if self._init_error:
            return GapReport(error=self._init_error)
        
        if not spec_text or not spec_text.strip():
            return GapReport(error="Specification text is empty.")
        
        # Load knowledge base for RAG-enhanced analysis
        knowledge = load_knowledge_base()
        
        # Build the prompt with optional knowledge injection
        if knowledge:
            knowledge_section = f"""Use the following Dafny Reference Rules to analyze the spec and suggest advanced invariants:

=== DAFNY REFERENCE ===
{knowledge}
=== END REFERENCE ===

"""
            prompt = f"{knowledge_section}{SYSTEM_PROMPT}\n\n---\nSPECIFICATION TO ANALYZE:\n---\n{spec_text}"
        else:
            # Fallback to standard prompt if no knowledge base
            prompt = f"{SYSTEM_PROMPT}\n\n---\nSPECIFICATION TO ANALYZE:\n---\n{spec_text}"
        
        try:
            # Call Gemini API with new SDK
            if not self._model:
                return GapReport(error="Model not configured")
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt
            )
            raw_text = response.text or ""
            
            # Parse the JSON response
            return self._parse_response(raw_text)
            
        except Exception as e:
            return GapReport(
                error=f"API call failed: {str(e)}",
                raw_response=str(e)
            )
    
    def _parse_response(self, raw_text: str) -> GapReport:
        """
        Parse the LLM response into a GapReport.
        
        Args:
            raw_text: The raw text response from the LLM.
            
        Returns:
            Parsed GapReport or report with error.
        """
        try:
            # Clean up the response - remove markdown code blocks if present
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # Parse JSON
            data = json.loads(cleaned)
            
            # Extract gaps
            gaps = []
            for gap_data in data.get("gaps", []):
                gaps.append(Gap(
                    severity=gap_data.get("severity", "warning"),
                    description=gap_data.get("description", "")
                ))
            
            # Extract ambiguities
            ambiguities = data.get("ambiguities", [])
            
            # Extract Dafny skeleton and unescape newlines
            dafny_skeleton = data.get("dafny_skeleton", "")
            if isinstance(dafny_skeleton, str):
                dafny_skeleton = dafny_skeleton.replace("\\n", "\n")
                # Strip any HTML tags that may have leaked from LLM output
                dafny_skeleton = re.sub(r'<[^>]+>', '', dafny_skeleton)
            
            # Extract tagged spec and unescape newlines
            tagged_spec = data.get("tagged_spec", "")
            if isinstance(tagged_spec, str):
                tagged_spec = tagged_spec.replace("\\n", "\n")
            
            # Extract traceability matrix
            traceability_matrix = []
            for entry_data in data.get("traceability_matrix", []):
                traceability_matrix.append(TraceabilityEntry(
                    id=entry_data.get("id", ""),
                    source_text=entry_data.get("source_text", ""),
                    status=entry_data.get("status", "Pending"),
                    code_line=entry_data.get("code_line", "")
                ))
            
            return GapReport(
                gaps=gaps,
                ambiguities=ambiguities,
                dafny_skeleton=dafny_skeleton,
                tagged_spec=tagged_spec,
                traceability_matrix=traceability_matrix,
                raw_response=raw_text
            )
            
        except json.JSONDecodeError as e:
            return GapReport(
                error=f"Failed to parse LLM response as JSON: {e}",
                raw_response=raw_text
            )
    
    def generate_suggestion(self, spec_text: str, gap: Gap) -> Optional[Suggestion]:
        """
        Generate an AI-powered fix suggestion for a specific gap.
        
        Args:
            spec_text: The current specification text
            gap: The Gap object to generate a fix for
            
        Returns:
            Suggestion object with fix details, or None if generation fails
        """
        # Check configuration
        if self._init_error:
            return None
        
        if not spec_text or not gap:
            return None
        
        # Build the prompt for suggestion generation
        suggestion_prompt = f"""You are a Tech Lead fixing specification gaps.

GAP: {gap.description}
SEVERITY: {gap.severity}

CURRENT SPECIFICATION:
---
{spec_text}
---

TASK: Identify the specific section of the specification that causes this gap and propose a minimal fix.

You MUST return ONLY valid JSON with this exact schema (no markdown, no explanation):
{{
  "original_text": "The exact text from the spec that needs to be fixed (must match verbatim)",
  "proposed_text": "The replacement text that fixes the gap",
  "rationale": "Brief explanation of how this fix addresses the gap"
}}

RULES:
- original_text MUST be an exact substring from the specification above
- Keep changes minimal and surgical - only fix what's necessary
- proposed_text should preserve the style and format of the original
- If the gap requires adding new text, set original_text to the nearest context and proposed_text to include both context and new content
- rationale should be concise (1-2 sentences)
"""
        
        try:
            # Call Gemini API
            if not self._model:
                return None
            response = self._client.models.generate_content(
                model=self._model,
                contents=suggestion_prompt
            )
            raw_text = response.text or ""
            
            # Parse the JSON response
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            data = json.loads(cleaned)
            
            # Create suggestion object
            return Suggestion(
                gap_id=f"{gap.severity}_{hash(gap.description) % 10000}",
                original_text=data.get("original_text", ""),
                proposed_text=data.get("proposed_text", ""),
                rationale=data.get("rationale", "")
            )
            
        except Exception:
            # Return None on error - caller can handle gracefully
            return None


def audit_specification(spec_text: str, api_key: Optional[str] = None) -> GapReport:
    """
    Convenience function to audit a specification.
    
    Args:
        spec_text: The specification text to analyze.
        api_key: Optional API key (uses environment if not provided).
        
    Returns:
        GapReport with analysis results.
    """
    auditor = SpecAuditor(api_key=api_key)
    return auditor.audit_spec(spec_text)


if __name__ == "__main__":
    # Simple test harness
    sample_spec = """
    The Rewards System allows users to earn points for completing tasks.
    Users can redeem points for rewards. Premium users get 2x points.
    """
    
    print("Testing Spec Auditor...")
    auditor = SpecAuditor()
    
    if not auditor.is_configured():
        print(f"Configuration Error: {auditor.get_configuration_error()}")
    else:
        print("Auditor configured successfully!")
        result = auditor.audit_spec(sample_spec)
        
        if result.error:
            print(f"Audit Error: {result.error}")
        else:
            print(f"\nFound {len(result.gaps)} gaps:")
            for gap in result.gaps:
                print(f"  [{gap.severity}] {gap.description}")
            
            print(f"\nFound {len(result.ambiguities)} ambiguities:")
            for amb in result.ambiguities:
                print(f"  - {amb}")
            
            print(f"\nDafny Skeleton:\n{result.dafny_skeleton}")
