"""
Harmonization Service - AI-Gapped Development Workflow

Implements the "Harmonize" workflow from the editing protocol:
1. Detect when spec.md changes vs core.dfy (desynchronization)
2. Analyze the diff to understand what changed
3. Update core.dfy incrementally based on changes
4. Run Dafny verification
5. Update generated Python code
6. Mark as synchronized when complete

This enforces the one-way flow: Spec → Dafny → Python
Users never edit code directly; they only modify specifications.
"""

import logging
import hashlib
import os
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from dataclasses import dataclass
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


@dataclass
class SpecChange:
    """Represents a detected change in the specification"""
    change_type: str  # 'addition', 'modification', 'deletion'
    section: str
    old_content: Optional[str]
    new_content: Optional[str]
    description: str


@dataclass
class HarmonizationResult:
    """Result of harmonization process"""
    success: bool
    sync_status: str  # 'clean', 'dirty', 'verifying', 'error'
    changes_detected: List[SpecChange]
    dafny_updated: bool
    verification_passed: bool
    verification_output: Optional[str]
    error_message: Optional[str]
    updated_files: List[str]
    duration_ms: int


class HarmonizationService:
    """Service for harmonizing specifications with implementation"""

    def __init__(self):
        """Initialize harmonization service"""
        self.model_name = "gemini-1.5-flash"

    def compute_hash(self, content: str) -> str:
        """
        Compute SHA256 hash of content

        Args:
            content: String content to hash

        Returns:
            Hex-encoded SHA256 hash with 'sha256:' prefix
        """
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return f"sha256:{hash_obj.hexdigest()}"

    def detect_desync(
        self,
        current_spec: str,
        current_dafny: str,
        stored_spec_hash: Optional[str],
        stored_dafny_hash: Optional[str]
    ) -> bool:
        """
        Detect if spec and Dafny are out of sync

        Args:
            current_spec: Current spec.md content
            current_dafny: Current core.dfy content
            stored_spec_hash: Last known spec hash
            stored_dafny_hash: Last known Dafny hash

        Returns:
            True if desynchronized, False if in sync
        """
        current_spec_hash = self.compute_hash(current_spec)
        current_dafny_hash = self.compute_hash(current_dafny)

        # If we don't have stored hashes, we can't detect desync
        if not stored_spec_hash or not stored_dafny_hash:
            logger.info("No stored hashes, assuming synchronized")
            return False

        # Check if spec changed but Dafny didn't
        spec_changed = current_spec_hash != stored_spec_hash
        dafny_changed = current_dafny_hash != stored_dafny_hash

        if spec_changed and not dafny_changed:
            logger.info("Desync detected: spec changed but Dafny unchanged")
            return True

        return False

    def analyze_spec_changes(
        self,
        old_spec: str,
        new_spec: str
    ) -> List[SpecChange]:
        """
        Analyze what changed between old and new spec

        Args:
            old_spec: Previous specification content
            new_spec: Current specification content

        Returns:
            List of detected changes
        """
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set, using simple diff")
            return self._simple_diff_analysis(old_spec, new_spec)

        try:
            model = genai.GenerativeModel(self.model_name)

            prompt = f"""Analyze the changes between these two specifications and identify what was modified.

OLD SPECIFICATION:
---
{old_spec}
---

NEW SPECIFICATION:
---
{new_spec}
---

Identify the key changes and categorize them as:
- ADDITION: New requirements or features added
- MODIFICATION: Existing requirements changed
- DELETION: Requirements removed

For each change, provide:
1. Type (ADDITION/MODIFICATION/DELETION)
2. Section affected (e.g., "Authentication", "Data Validation")
3. Description of the change

Format your response as JSON:
{{
  "changes": [
    {{
      "type": "ADDITION|MODIFICATION|DELETION",
      "section": "section name",
      "description": "brief description of change"
    }}
  ]
}}

Focus on semantic changes, not formatting or whitespace changes.
"""

            response = model.generate_content(prompt)
            result_text = response.text.strip()

            # Parse JSON response
            import json
            # Clean markdown code fences if present
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            result_json = json.loads(result_text)

            changes = []
            for change_data in result_json.get("changes", []):
                changes.append(SpecChange(
                    change_type=change_data["type"].lower(),
                    section=change_data["section"],
                    old_content=None,  # Could extract from diff if needed
                    new_content=None,
                    description=change_data["description"]
                ))

            return changes

        except Exception as e:
            logger.error(f"Failed to analyze spec changes with AI: {e}")
            return self._simple_diff_analysis(old_spec, new_spec)

    def _simple_diff_analysis(self, old_spec: str, new_spec: str) -> List[SpecChange]:
        """
        Simple diff analysis when AI is not available

        Args:
            old_spec: Old specification
            new_spec: New specification

        Returns:
            List of changes (simplified)
        """
        # If specs are identical, return empty list
        if old_spec == new_spec:
            return []

        old_lines = set(old_spec.split("\n"))
        new_lines = set(new_spec.split("\n"))

        added_lines = new_lines - old_lines
        removed_lines = old_lines - new_lines

        changes = []

        if added_lines:
            changes.append(SpecChange(
                change_type="addition",
                section="General",
                old_content=None,
                new_content="\n".join(list(added_lines)[:3]),  # First 3 lines
                description=f"{len(added_lines)} lines added"
            ))

        if removed_lines:
            changes.append(SpecChange(
                change_type="deletion",
                section="General",
                old_content="\n".join(list(removed_lines)[:3]),
                new_content=None,
                description=f"{len(removed_lines)} lines removed"
            ))

        if not changes:
            changes.append(SpecChange(
                change_type="modification",
                section="General",
                old_content=None,
                new_content=None,
                description="Minor modifications detected"
            ))

        return changes

    def update_dafny_incrementally(
        self,
        current_dafny: str,
        spec_changes: List[SpecChange],
        new_spec: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Update Dafny code incrementally based on spec changes

        Args:
            current_dafny: Current Dafny code
            spec_changes: List of detected changes
            new_spec: New specification content

        Returns:
            Tuple of (success, updated_dafny, error_message)
        """
        if not GEMINI_API_KEY:
            error = "GEMINI_API_KEY not set, cannot update Dafny"
            logger.error(error)
            return False, current_dafny, error

        try:
            model = genai.GenerativeModel(self.model_name)

            # Build change summary
            change_summary = "\n".join([
                f"- {change.change_type.upper()}: {change.section} - {change.description}"
                for change in spec_changes
            ])

            prompt = f"""You are updating Dafny formal verification code based on specification changes.

CURRENT DAFNY CODE:
---
{current_dafny}
---

NEW SPECIFICATION:
---
{new_spec}
---

DETECTED CHANGES:
{change_summary}

Task: Update the Dafny code to reflect the specification changes.

Requirements:
1. Preserve existing verified code where possible (incremental update)
2. Add new methods/predicates for new requirements
3. Update existing methods if requirements changed
4. Remove methods for deleted requirements
5. Ensure all preconditions, postconditions, and invariants are valid
6. Maintain Dafny syntax correctness

IMPORTANT:
- Return ONLY the updated Dafny code, no explanations
- Do not include markdown code fences
- Ensure the code will verify in Dafny

Output the complete updated Dafny code:
"""

            response = model.generate_content(prompt)
            updated_dafny = response.text.strip()

            # Clean markdown code fences if present
            updated_dafny = updated_dafny.replace("```dafny", "").replace("```", "").strip()

            logger.info(f"Updated Dafny code ({len(updated_dafny)} chars)")
            return True, updated_dafny, None

        except Exception as e:
            error = f"Failed to update Dafny code: {str(e)}"
            logger.error(error)
            return False, current_dafny, error

    def harmonize(
        self,
        old_spec: str,
        new_spec: str,
        current_dafny: str,
        verify_callback: Optional[callable] = None
    ) -> HarmonizationResult:
        """
        Execute full harmonization workflow

        Args:
            old_spec: Previous specification
            new_spec: Current specification
            current_dafny: Current Dafny code
            verify_callback: Optional function to call for Dafny verification

        Returns:
            HarmonizationResult with details of harmonization
        """
        start_time = datetime.now()

        try:
            # Step 1: Analyze changes
            logger.info("Step 1: Analyzing specification changes...")
            changes = self.analyze_spec_changes(old_spec, new_spec)

            if not changes:
                logger.info("No changes detected")
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return HarmonizationResult(
                    success=True,
                    sync_status='clean',
                    changes_detected=[],
                    dafny_updated=False,
                    verification_passed=True,
                    verification_output="No changes needed",
                    error_message=None,
                    updated_files=[],
                    duration_ms=int(duration)
                )

            # Step 2: Update Dafny code
            logger.info(f"Step 2: Updating Dafny code ({len(changes)} changes)...")
            success, updated_dafny, error = self.update_dafny_incrementally(
                current_dafny,
                changes,
                new_spec
            )

            if not success:
                duration = (datetime.now() - start_time).total_seconds() * 1000
                return HarmonizationResult(
                    success=False,
                    sync_status='error',
                    changes_detected=changes,
                    dafny_updated=False,
                    verification_passed=False,
                    verification_output=None,
                    error_message=error,
                    updated_files=[],
                    duration_ms=int(duration)
                )

            # Step 3: Verify Dafny code (if callback provided)
            verification_passed = True
            verification_output = None

            if verify_callback:
                logger.info("Step 3: Verifying Dafny code...")
                try:
                    verification_result = verify_callback(updated_dafny)
                    verification_passed = verification_result.get('success', False)
                    verification_output = verification_result.get('output', '')
                except Exception as e:
                    logger.error(f"Verification failed: {e}")
                    verification_passed = False
                    verification_output = str(e)
            else:
                logger.info("Step 3: Skipping verification (no callback)")

            # Determine final status
            if verification_passed:
                sync_status = 'clean'
                error_message = None
            else:
                sync_status = 'error'
                error_message = f"Verification failed: {verification_output}"

            duration = (datetime.now() - start_time).total_seconds() * 1000

            return HarmonizationResult(
                success=verification_passed,
                sync_status=sync_status,
                changes_detected=changes,
                dafny_updated=True,
                verification_passed=verification_passed,
                verification_output=verification_output,
                error_message=error_message,
                updated_files=['core.dfy'],
                duration_ms=int(duration)
            )

        except Exception as e:
            logger.error(f"Harmonization failed: {e}")
            duration = (datetime.now() - start_time).total_seconds() * 1000

            return HarmonizationResult(
                success=False,
                sync_status='error',
                changes_detected=[],
                dafny_updated=False,
                verification_passed=False,
                verification_output=None,
                error_message=str(e),
                updated_files=[],
                duration_ms=int(duration)
            )


# Singleton instance
_harmonization_instance = None


def get_harmonization_service() -> HarmonizationService:
    """Get or create harmonization service singleton"""
    global _harmonization_instance
    if _harmonization_instance is None:
        _harmonization_instance = HarmonizationService()
    return _harmonization_instance
