"""
Specification generation service.
Handles specification triage, structuring, auditing, and unit deconstruction.
This service bridges the Imperative Shell (HTTP/DB) and Functional Core (workflow/auditor).
"""

import logging
import os
import re
import uuid
from typing import Optional, List, Tuple, Literal, cast

from sqlalchemy.orm import Session
from fastapi import HTTPException

from core.workflow import run_triage, run_structuring, TriageResult, StructureResult
from core.auditor import SpecAuditor, GapReport
from api.database import File as DBFile, UnitLink as DBUnitLink, Project as DBProject
from api.deconstruct import UnitIdentifier, extract_content_by_lines, create_unit_filename
from api.files import get_project_owner_filter, hash_api_key
from api.models import (
    GenerateSpecRequest,
    GenerateSpecResponse,
    FindGapsRequest,
    FindGapsResponse,
    RefineSpecRequest,
    RefineSpecResponse,
    Gap,
    GapLocation,
    Ambiguity,
    TraceabilityEntry,
    SpecStatistics,
    UnitInfo,
)

logger = logging.getLogger(__name__)


class SpecGeneratorService:
    """
    Service for generating formal specifications from English requirements.
    
    This service orchestrates the workflow stages:
    1. Triage: Classify input document type
    2. Structure: Normalize to standard template
    3. Audit: Analyze gaps and generate Dafny code
    4. Deconstruct: Extract units if applicable
    """
    
    def __init__(self, db: Session, current_user=None):
        """
        Initialize the service.
        
        Args:
            db: Database session
            current_user: Current authenticated user (optional)
        """
        self.db = db
        self.current_user = current_user
    
    def generate_spec(
        self,
        request: GenerateSpecRequest,
        api_key: str
    ) -> GenerateSpecResponse:
        """
        Generate formal specification from English requirements.
        
        Args:
            request: Generation request with English spec
            api_key: API key for authentication
            
        Returns:
            GenerateSpecResponse with structured spec, Dafny code, and metadata
        """
        # Stage 1: Triage
        triage_result = self._triage_request(request.english_spec)
        if triage_result.error:
            raise HTTPException(status_code=400, detail=triage_result.error)
        
        # Stage 2: Structure
        structure_result = self._structure_content(request.english_spec)
        if structure_result.error:
            raise HTTPException(status_code=400, detail=structure_result.error)
        
        # Suggest filename if generic
        suggested_filename = self._suggest_filename(
            structure_result.structured_spec,
            request.current_filename or ""
        )
        
        # Stage 3: Audit
        audit_result = self._audit_content(structure_result.structured_spec)
        if audit_result.error:
            raise HTTPException(status_code=500, detail=audit_result.error)
        
        # Build traceability matrix
        enhanced_traceability = self._build_traceability_matrix(audit_result)
        
        # Calculate statistics
        statistics = self._calculate_statistics(enhanced_traceability)
        
        # Stage 4: Unit deconstruction (if applicable)
        units_created = None
        subfolder_name = None
        
        if request.project_id and request.source_file_id:
            units_created, subfolder_name = self._deconstruct_units(
                request.project_id,
                request.source_file_id,
                structure_result.structured_spec,
                audit_result,
                suggested_filename or request.current_filename or "spec",
                api_key
            )
        
        # Determine Dafny skeleton to return
        dafny_skeleton_to_return = "" if units_created else audit_result.dafny_skeleton
        
        return GenerateSpecResponse(
            triage={
                "doc_type": triage_result.doc_type.value if triage_result.doc_type else "junk",
                "confidence": triage_result.confidence,
                "detected_patterns": []
            },
            structured_spec=structure_result.structured_spec,
            dafny_skeleton=dafny_skeleton_to_return,
            gaps=[],  # Gaps are now separate via find_gaps endpoint
            ambiguities=[],
            traceability_matrix=enhanced_traceability,
            statistics=statistics,
            suggested_filename=suggested_filename,
            units_created=units_created,
            subfolder_name=subfolder_name
        )
    
    def find_gaps(self, request: FindGapsRequest) -> FindGapsResponse:
        """
        Find gaps and ambiguities in a specification without generating Dafny code.
        
        Args:
            request: Find gaps request with spec text
            
        Returns:
            FindGapsResponse with gaps, ambiguities, and statistics
        """
        # Stage 1: Structure the spec
        structure_result = self._structure_content(request.spec)
        if structure_result.error:
            raise HTTPException(status_code=400, detail=structure_result.error)
        
        # Stage 2: Audit to find gaps
        auditor = SpecAuditor()
        if not auditor.is_configured():
            raise HTTPException(
                status_code=500,
                detail=auditor.get_configuration_error()
            )
        
        audit_result = auditor.audit_spec(structure_result.structured_spec)
        if audit_result.error:
            raise HTTPException(status_code=500, detail=audit_result.error)
        
        # Enhanced gap processing with IDs and locations
        enhanced_gaps = []
        for idx, gap in enumerate(audit_result.gaps):
            enhanced_gaps.append(Gap(
                id=f"GAP-{idx+1:03d}",
                severity=cast(Literal["critical", "high", "medium", "low"], gap.severity if gap.severity in ["critical", "high", "medium", "low"] else "medium"),
                category="incomplete-spec",
                description=gap.description,
                location=GapLocation(line=None, column=None, file=None),
                suggestion=f"Consider adding more details about: {gap.description[:50]}...",
                code_snippet=None
            ))
        
        # Enhanced ambiguities with IDs
        enhanced_ambiguities = []
        for idx, amb_text in enumerate(audit_result.ambiguities):
            enhanced_ambiguities.append(Ambiguity(
                id=f"AMB-{idx+1:03d}",
                text=amb_text,
                possible_interpretations=["Interpretation A", "Interpretation B"],
                recommendation="Please clarify this requirement"
            ))
        
        # Calculate statistics
        total_reqs = len(audit_result.traceability_matrix)
        mapped_reqs = sum(1 for entry in audit_result.traceability_matrix if entry.status == "mapped")
        coverage = (mapped_reqs / total_reqs * 100) if total_reqs > 0 else 0.0
        critical_gaps = sum(1 for g in enhanced_gaps if g.severity == "critical")
        
        statistics = SpecStatistics(
            total_requirements=total_reqs,
            mapped_requirements=mapped_reqs,
            coverage_percentage=round(coverage, 2),
            total_gaps=len(enhanced_gaps),
            critical_gaps=critical_gaps
        )
        
        return FindGapsResponse(
            gaps=enhanced_gaps,
            ambiguities=enhanced_ambiguities,
            statistics=statistics
        )
    
    def refine_spec(self, request: RefineSpecRequest) -> RefineSpecResponse:
        """
        Refine a specification by applying gap suggestions.
        
        Args:
            request: Refinement request with spec and gaps to apply
            
        Returns:
            RefineSpecResponse with refined specification
        """
        auditor = SpecAuditor()
        
        if not auditor.is_configured():
            raise HTTPException(
                status_code=500,
                detail=auditor.get_configuration_error()
            )
        
        # Filter gaps to apply
        gaps_to_apply = request.gaps
        if request.apply_gap_ids:
            gaps_to_apply = [gap for gap in request.gaps if gap.id in request.apply_gap_ids]
        
        if not gaps_to_apply:
            # No gaps to apply, return original spec
            return RefineSpecResponse(
                refined_spec=request.spec,
                applied_gaps=[]
            )
        
        # Build prompt for Gemini to refine the spec
        gap_descriptions = "\n".join([
            f"- {gap.id} ({gap.severity}): {gap.description}\n  Suggestion: {gap.suggestion or 'No specific suggestion'}"
            for gap in gaps_to_apply
        ])
        
        prompt = f"""You are refining a formal specification document based on identified gaps.

ORIGINAL SPECIFICATION:
{request.spec}

IDENTIFIED GAPS TO ADDRESS:
{gap_descriptions}

TASK:
Refine the original specification by addressing the gaps listed above. Apply the suggestions provided for each gap.
- Keep the overall structure and style of the original specification
- Integrate the improvements naturally into the existing text
- Maintain consistency with the original document's tone and format
- Do not add new sections unless necessary to address the gaps
- Preserve all existing content that is not related to the gaps

Return the complete refined specification:
"""
        
        try:
            if not auditor._model:
                raise HTTPException(status_code=500, detail="Gemini model not configured")
            response = auditor._client.models.generate_content(
                model=auditor._model,
                contents=prompt
            )
            refined_spec = (response.text or "").strip()
            
            # Clean up markdown code blocks if present
            if refined_spec.startswith("```"):
                lines = refined_spec.split("\n")
                # Remove first line (```markdown or similar)
                if len(lines) > 1:
                    lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                refined_spec = "\n".join(lines)
            
            return RefineSpecResponse(
                refined_spec=refined_spec,
                applied_gaps=gaps_to_apply
            )
        except Exception as e:
            logger.error(f"Spec refinement failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to refine specification: {str(e)}"
            )
    
    def _triage_request(self, english_spec: str) -> TriageResult:
        """
        Stage 1: Triage the input to classify document type.
        
        Args:
            english_spec: Raw English specification text
            
        Returns:
            TriageResult with doc_type and confidence
        """
        return run_triage(english_spec)
    
    def _structure_content(self, english_spec: str) -> StructureResult:
        """
        Stage 2: Structure the specification into standard template.
        
        Args:
            english_spec: Raw English specification text
            
        Returns:
            StructureResult with structured specification
        """
        return run_structuring(english_spec)
    
    def _audit_content(self, structured_spec: str) -> GapReport:
        """
        Stage 3: Audit the structured specification.
        
        Args:
            structured_spec: Structured specification text
            
        Returns:
            GapReport with gaps, ambiguities, and Dafny skeleton
        """
        auditor = SpecAuditor()
        if not auditor.is_configured():
            raise HTTPException(
                status_code=500,
                detail=auditor.get_configuration_error()
            )
        
        return auditor.audit_spec(structured_spec)
    
    def _suggest_filename(
        self,
        structured_spec: str,
        current_filename: str
    ) -> Optional[str]:
        """
        Suggest a filename if the current filename is generic.
        
        Args:
            structured_spec: Structured specification text
            current_filename: Current filename (may be generic)
            
        Returns:
            Suggested filename or None
        """
        if not current_filename:
            return None
        
        # Check if filename is generic (untitled-*, new-file-*, etc.)
        generic_patterns = [r'^untitled-', r'^new-file-', r'^untitled\d+', r'^new\d+']
        is_generic = any(re.match(pattern, current_filename.lower()) for pattern in generic_patterns)
        
        if not is_generic:
            return None
        
        # Suggest filename using Gemini
        auditor_temp = SpecAuditor()
        if not auditor_temp.is_configured():
            return None
        
        try:
            prompt = f"""Based on this specification, suggest a concise, descriptive filename (without extension).
Return ONLY the filename, no path, no extension, no quotes, no markdown.
Examples: token-minting-spec, authentication-requirements, payment-processing

SPECIFICATION:
{structured_spec[:2000]}

Filename:"""
            if not auditor_temp._model:
                return None
            response = auditor_temp._client.models.generate_content(
                model=auditor_temp._model,
                contents=prompt
            )
            suggested_filename = (response.text or "").strip().strip('"').strip("'").strip()
            # Clean up any markdown or extra text
            if suggested_filename.startswith("```"):
                suggested_filename = suggested_filename.split("\n")[0].replace("```", "").strip()
            suggested_filename = re.sub(r'[^a-z0-9-]', '', suggested_filename.lower())[:50]
            return suggested_filename if suggested_filename else None
        except Exception as e:
            logger.warning(f"Filename suggestion failed: {e}")
            return None
    
    def _deconstruct_units(
        self,
        project_id: str,
        source_file_id: str,
        structured_spec: str,
        audit_result: GapReport,
        filename_base: str,
        api_key: str
    ) -> Tuple[Optional[List[UnitInfo]], Optional[str]]:
        """
        Stage 4: Deconstruct specification into units if applicable.
        
        Args:
            project_id: Project ID to save units to
            source_file_id: Source file ID being deconstructed
            structured_spec: Structured specification text
            audit_result: Audit result with Dafny skeleton
            filename_base: Base filename for subfolder naming
            api_key: API key for authentication
            
        Returns:
            Tuple of (units_created list, subfolder_name) or (None, None)
        """
        try:
            # Verify project ownership
            api_key_hash_value = hash_api_key(api_key) if api_key else None
            owner_filter = get_project_owner_filter(self.current_user, api_key_hash_value)
            project = self.db.query(DBProject).filter(
                DBProject.project_id == project_id,
                owner_filter
            ).first()
            
            if not project:
                logger.warning(f"Project {project_id} not found or unauthorized for unit deconstruction")
                return None, None
            
            # Load source file
            source_file = self.db.query(DBFile).filter(
                DBFile.file_id == source_file_id,
                DBFile.project_id == project_id
            ).first()
            
            if not source_file or source_file.file_type != 'md':
                return None, None
            
            # Identify units
            identifier = UnitIdentifier()
            try:
                unit_candidates = identifier.identify_units(str(source_file.content))  # type: ignore[arg-type]
                
                if not unit_candidates or len(unit_candidates) == 0:
                    return None, None
                
                # Determine subfolder name
                filename_base_clean = os.path.splitext(filename_base)[0] if '.' in filename_base else filename_base
                subfolder_name = f"{filename_base_clean}-units"
                
                # Process each unit
                created_units = []
                successful_count = 0
                auditor = SpecAuditor()
                
                for idx, candidate in enumerate(unit_candidates, start=1):
                    try:
                        # Extract unit content
                        unit_content = extract_content_by_lines(
                            str(source_file.content),  # type: ignore[arg-type]
                            candidate.line_range[0],
                            candidate.line_range[1]
                        )
                        
                        # Structure unit content
                        unit_structure_result = run_structuring(unit_content)
                        if unit_structure_result.error:
                            logger.warning(f"Unit {idx} structuring failed: {unit_structure_result.error}")
                            continue
                        
                        # Audit unit spec to get formal spec with anchors and Dafny
                        unit_audit_result = auditor.audit_spec(unit_structure_result.structured_spec)
                        if unit_audit_result.error:
                            logger.warning(f"Unit {idx} audit failed: {unit_audit_result.error}")
                            continue
                        
                        dafny_code = unit_audit_result.dafny_skeleton
                        formal_spec = unit_audit_result.tagged_spec or unit_structure_result.structured_spec
                        
                        # Create filenames with subfolder
                        unit_filename = create_unit_filename(idx, candidate.title, ".unit.md", subfolder_name)
                        dafny_filename = create_unit_filename(idx, candidate.title, ".dfy", subfolder_name)
                        
                        # Create unit markdown content
                        unit_markdown = f"""# Unit: {candidate.title}

## Description
{candidate.description}

## Requirements
{chr(10).join(f"- {req}" for req in candidate.requirements)}

## Dependencies
{chr(10).join(f"- {dep}" for dep in candidate.dependencies) if candidate.dependencies else "None"}

## Formal Specification
{formal_spec}
"""
                        
                        # Save unit markdown file
                        unit_file_id = str(uuid.uuid4())
                        unit_file = DBFile(
                            file_id=unit_file_id,
                            project_id=source_file.project_id,
                            filename=unit_filename,
                            content=unit_markdown,
                            file_type='unit',
                            size_bytes=len(unit_markdown.encode('utf-8'))
                        )
                        self.db.add(unit_file)
                        
                        # Save Dafny file
                        dafny_file_id = str(uuid.uuid4())
                        dafny_file = DBFile(
                            file_id=dafny_file_id,
                            project_id=source_file.project_id,
                            filename=dafny_filename,
                            content=dafny_code,
                            file_type='dfy',
                            size_bytes=len(dafny_code.encode('utf-8'))
                        )
                        self.db.add(dafny_file)
                        
                        # Create unit link
                        link_id = str(uuid.uuid4())
                        unit_link = DBUnitLink(
                            link_id=link_id,
                            root_file_id=source_file.file_id,
                            unit_file_id=unit_file_id,
                            dafny_file_id=dafny_file_id,
                            start_line=candidate.line_range[0],
                            end_line=candidate.line_range[1],
                            title=candidate.title,
                            verification_status='unknown'
                        )
                        self.db.add(unit_link)
                        
                        self.db.commit()
                        
                        # Add to response
                        created_units.append(UnitInfo(
                            unit_id=unit_file_id,
                            unit_filename=unit_filename,
                            dafny_filename=dafny_filename,
                            title=candidate.title,
                            description=candidate.description,
                            requirements=candidate.requirements,
                            dafny_code=dafny_code,
                            line_range=candidate.line_range
                        ))
                        
                        successful_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to create unit {idx}: {e}")
                        self.db.rollback()
                        continue
                
                if created_units:
                    logger.info(f"Created {successful_count} units in subfolder {subfolder_name}")
                    return created_units, subfolder_name
                
                return None, None
                
            except Exception as e:
                logger.warning(f"Unit identification failed: {e}")
                return None, None
                
        except Exception as e:
            logger.error(f"Unit deconstruction error: {e}")
            return None, None
    
    def _build_traceability_matrix(self, audit_result: GapReport) -> List[TraceabilityEntry]:
        """
        Build enhanced traceability matrix from audit result.
        
        Args:
            audit_result: Audit result with traceability matrix
            
        Returns:
            List of TraceabilityEntry objects
        """
        enhanced_traceability = []
        for idx, entry in enumerate(audit_result.traceability_matrix):
            enhanced_traceability.append(TraceabilityEntry(
                id=entry.id,
                source_text=entry.source_text,
                code_line=entry.code_line,
                line_number=entry.line_number,
                status=cast(Literal["mapped", "partial", "missing"], entry.status if entry.status in ["mapped", "partial", "missing"] else "mapped"),
                confidence=0.9
            ))
        return enhanced_traceability
    
    def _calculate_statistics(
        self,
        traceability_matrix: List[TraceabilityEntry]
    ) -> SpecStatistics:
        """
        Calculate specification statistics from traceability matrix.
        
        Args:
            traceability_matrix: List of traceability entries
            
        Returns:
            SpecStatistics object
        """
        total_reqs = len(traceability_matrix)
        mapped_reqs = sum(1 for e in traceability_matrix if e.status == "mapped")
        coverage = (mapped_reqs / total_reqs * 100) if total_reqs > 0 else 0.0
        
        return SpecStatistics(
            total_requirements=total_reqs,
            mapped_requirements=mapped_reqs,
            coverage_percentage=round(coverage, 2),
            total_gaps=0,  # Gaps are now separate
            critical_gaps=0
        )
