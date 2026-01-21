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
    import google.generativeai as genai
except ImportError:
    genai = None

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Gap:
    """Represents a single logic gap found in a specification."""
    severity: str  # "critical" or "warning"
    description: str


@dataclass
class GapReport:
    """
    Represents the full audit report for a specification.
    
    Attributes:
        gaps: List of logic gaps (critical issues, missing validations)
        ambiguities: List of vague or unclear definitions
        dafny_skeleton: Generated Dafny trait code skeleton
        raw_response: The raw LLM response for debugging
        error: Error message if the audit failed
    """
    gaps: list[Gap] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    dafny_skeleton: str = ""
    raw_response: str = ""
    error: Optional[str] = None


# System prompt for the LLM
SYSTEM_PROMPT = """You are a Senior Formal Verification Engineer specializing in smart contract security and formal methods.

Analyze the following specification text for:
1. **Critical Logic Gaps**: Missing validations (negative numbers, zero amounts, null checks), race conditions, missing edge cases, exploitable logic holes
2. **Ambiguities**: Vague definitions, unclear state transitions, undefined terms
3. **Missing Preconditions/Postconditions**: What should be guaranteed before and after operations

Based on your analysis, generate a Dafny trait skeleton that would formally specify this system.

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
  "dafny_skeleton": "trait SpecName {\\n  // Dafny code here\\n}"
}

Rules:
- severity must be either "critical" or "warning"
- Find at least 2-3 gaps if the spec has any complexity
- The dafny_skeleton should include method signatures with requires/ensures clauses
- Use \\n for newlines in the dafny_skeleton string

CRITICAL Dafny Rules for Map Operations:
- If a method transforms a map (e.g., returns new_db from db), you MUST add a STRUCTURAL INTEGRITY clause:
  ensures success ==> (forall k :: k in db <==> k in new_db)
  This tells Dafny that keys are preserved, which is required before accessing new_db[key] in other ensures clauses.
- Always add requires clauses for map key existence BEFORE accessing map values (e.g., requires sender in db)
- Order of ensures clauses matters: structural integrity FIRST, then value-based postconditions"""


def load_knowledge_base(path: str = None) -> Optional[str]:
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
    
    DEFAULT_MODEL = "gemini-2.0-flash"
    FALLBACK_MODEL = "gemini-1.5-flash"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the auditor with an API key.
        
        Args:
            api_key: Google Gemini API key. If not provided, reads from 
                     GEMINI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model = None
        
        if genai is None:
            self._init_error = "google-generativeai package not installed. Run: pip install google-generativeai"
        elif not self.api_key:
            self._init_error = "GEMINI_API_KEY not found. Set it in .env file or environment."
        else:
            self._init_error = None
            self._configure_genai()
    
    def _configure_genai(self) -> None:
        """Configure the Gemini API with the provided key."""
        if genai and self.api_key:
            genai.configure(api_key=self.api_key)
            try:
                self._model = genai.GenerativeModel(self.DEFAULT_MODEL)
            except Exception:
                # Fallback to older model if 2.0-flash not available
                try:
                    self._model = genai.GenerativeModel(self.FALLBACK_MODEL)
                except Exception as e:
                    self._init_error = f"Failed to initialize model: {e}"
    
    def is_configured(self) -> bool:
        """Check if the auditor is properly configured."""
        return self._init_error is None and self._model is not None
    
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
            # Call Gemini API
            response = self._model.generate_content(prompt)
            raw_text = response.text
            
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
            
            return GapReport(
                gaps=gaps,
                ambiguities=ambiguities,
                dafny_skeleton=dafny_skeleton,
                raw_response=raw_text
            )
            
        except json.JSONDecodeError as e:
            return GapReport(
                error=f"Failed to parse LLM response as JSON: {e}",
                raw_response=raw_text
            )


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
