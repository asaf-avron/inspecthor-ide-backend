"""
Deconstruction endpoint for breaking down specifications into verifiable units
Handles AI-powered unit identification, file creation, and traceability link generation
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
import uuid
import json
import re
import time
from typing import List, Optional
from datetime import datetime

from api.database import get_db, hash_api_key, File as DBFile, UnitLink as DBUnitLink
from api.models import (
    DeconstructRequest,
    DeconstructResponse,
    UnitInfo,
    UnitLinkInfo,
    DeconstructStats,
    UnitCandidate,
    TraceabilityResponse,
    TraceabilityLink
)
from core.auditor import SpecAuditor

router = APIRouter(prefix="/api", tags=["deconstruct"])


def get_api_key_from_header(
    x_api_key: Optional[str] = Header(None),
    request: Request = None
) -> str:
    """
    Extract API key or generate anonymous session key.
    For anonymous users (local-first), creates a session key based on IP.
    For authenticated users, uses provided API key.
    """
    if x_api_key:
        return x_api_key
    
    # Anonymous user - generate session key from IP
    if request and request.client:
        client_ip = request.client.host
        return f"anon_{client_ip}"
    
    return "anon_default"


class UnitIdentifier:
    """
    AI-powered unit identifier that analyzes markdown specifications
    and identifies logical boundaries for independent verification units.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Gemini API key"""
        self.auditor = SpecAuditor(api_key=api_key)
        
    def identify_units(self, markdown_content: str) -> List[UnitCandidate]:
        """
        Identify logical units in the markdown specification.
        
        Args:
            markdown_content: The full markdown specification text
            
        Returns:
            List of UnitCandidate objects with line ranges and metadata
        """
        if not self.auditor.is_configured():
            raise ValueError(self.auditor.get_configuration_error())
        
        # Build the AI prompt for unit identification
        prompt = f"""Analyze this specification and identify independent logical units that can be verified separately.

For each unit, return a JSON array with objects containing:
- title: Clear descriptive name (e.g., "Token Minting Logic")
- description: One-sentence summary
- requirements: List of requirement sentences extracted from this section
- start_line: Line number where unit begins (1-indexed)
- end_line: Line number where unit ends (1-indexed)
- dependencies: List of other unit titles this depends on (empty array if none)

CRITICAL RULES:
1. Units should align with major sections (## headers)
2. Line ranges must NOT overlap
3. Line numbers must be within bounds (1 to {len(markdown_content.splitlines())})
4. Each unit must have at least 1 requirement
5. Prefer larger, cohesive units over tiny fragments
6. Return ONLY valid JSON, no markdown formatting

SPECIFICATION TEXT:
---
{markdown_content}
---

Return JSON array of units:"""

        try:
            # Call Gemini API
            response = self.auditor._client.models.generate_content(
                model=self.auditor._model,
                contents=prompt
            )
            raw_text = response.text
            
            # Clean up response
            cleaned = raw_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            # Parse JSON
            units_data = json.loads(cleaned)
            
            # Convert to UnitCandidate objects
            candidates = []
            for unit_data in units_data:
                candidate = UnitCandidate(
                    title=unit_data.get("title", "Untitled Unit"),
                    description=unit_data.get("description", ""),
                    requirements=unit_data.get("requirements", []),
                    line_range=[
                        unit_data.get("start_line", 1),
                        unit_data.get("end_line", 1)
                    ],
                    dependencies=unit_data.get("dependencies", [])
                )
                candidates.append(candidate)
            
            # Validate units
            self._validate_units(candidates, len(markdown_content.splitlines()))
            
            return candidates
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse AI response as JSON: {e}")
        except Exception as e:
            raise ValueError(f"Unit identification failed: {e}")
    
    def _validate_units(self, units: List[UnitCandidate], total_lines: int) -> None:
        """
        Validate that units don't overlap and are within bounds.
        
        Args:
            units: List of unit candidates
            total_lines: Total number of lines in the source file
        """
        # Check line bounds
        for unit in units:
            start, end = unit.line_range
            if start < 1 or end > total_lines:
                raise ValueError(
                    f"Unit '{unit.title}' has invalid line range [{start}, {end}]. "
                    f"File has {total_lines} lines."
                )
            if start > end:
                raise ValueError(
                    f"Unit '{unit.title}' has invalid range: start ({start}) > end ({end})"
                )
            if len(unit.requirements) == 0:
                raise ValueError(
                    f"Unit '{unit.title}' has no requirements. Each unit must have at least one."
                )
        
        # Check for overlaps
        for i, unit1 in enumerate(units):
            for unit2 in units[i+1:]:
                start1, end1 = unit1.line_range
                start2, end2 = unit2.line_range
                
                # Check if ranges overlap
                if not (end1 < start2 or end2 < start1):
                    raise ValueError(
                        f"Units '{unit1.title}' and '{unit2.title}' have overlapping line ranges"
                    )


def extract_content_by_lines(content: str, start_line: int, end_line: int) -> str:
    """
    Extract content from specific line range.
    
    Args:
        content: Full text content
        start_line: Starting line (1-indexed)
        end_line: Ending line (1-indexed, inclusive)
        
    Returns:
        Extracted content
    """
    lines = content.splitlines()
    # Convert to 0-indexed and ensure bounds
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    return "\n".join(lines[start_idx:end_idx])


def create_unit_filename(index: int, title: str, extension: str) -> str:
    """
    Create filename for unit file.
    
    Args:
        index: Sequential unit number (1-indexed)
        title: Unit title
        extension: File extension (.unit.md or .dfy)
        
    Returns:
        Formatted filename
    """
    # Slugify title
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    slug = slug[:50]  # Limit length
    return f"unit-{index:03d}-{slug}{extension}"


@router.post("/deconstruct", response_model=DeconstructResponse)
async def deconstruct_specification(
    request: DeconstructRequest,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Deconstruct a specification file into verifiable units.
    
    Creates unit markdown files, generates Dafny code for each unit,
    and establishes traceability links with line-level precision.
    """
    start_time = time.time()
    api_key_hash_value = hash_api_key(api_key)
    
    # Load source file
    source_file = db.query(DBFile).filter(
        DBFile.file_id == request.source_file_id
    ).first()
    
    if not source_file:
        raise HTTPException(status_code=404, detail="Source file not found")
    
    # Verify project ownership
    if str(source_file.project_id) != request.project_id:
        raise HTTPException(
            status_code=400,
            detail="Source file does not belong to specified project"
        )
    
    # Verify file type
    if source_file.file_type != 'md':
        raise HTTPException(
            status_code=400,
            detail="Only markdown files can be deconstructed"
        )
    
    # Initialize unit identifier
    identifier = UnitIdentifier(api_key=api_key)
    auditor = SpecAuditor(api_key=api_key)
    
    if not auditor.is_configured():
        raise HTTPException(
            status_code=500,
            detail=auditor.get_configuration_error()
        )
    
    # Identify units
    try:
        unit_candidates = identifier.identify_units(source_file.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Apply max_units limit if specified
    if request.max_units and request.max_units > 0:
        unit_candidates = unit_candidates[:request.max_units]
    
    # Process each unit
    created_units = []
    created_links = []
    errors = []
    successful_count = 0
    failed_count = 0
    
    for idx, candidate in enumerate(unit_candidates, start=1):
        try:
            # Extract content for this unit
            unit_content = extract_content_by_lines(
                source_file.content,
                candidate.line_range[0],
                candidate.line_range[1]
            )
            
            # Create unit markdown content
            unit_markdown = f"""# Unit: {candidate.title}

## Description
{candidate.description}

## Requirements
{chr(10).join(f"- {req}" for req in candidate.requirements)}

## Dependencies
{chr(10).join(f"- {dep}" for dep in candidate.dependencies) if candidate.dependencies else "None"}

## Extracted Content
{unit_content}
"""
            
            # Generate Dafny code for this unit
            audit_result = auditor.audit_spec(unit_markdown)
            
            if audit_result.error:
                errors.append(f"Unit '{candidate.title}': Dafny generation failed - {audit_result.error}")
                failed_count += 1
                continue
            
            dafny_code = audit_result.dafny_skeleton
            
            # Create filenames
            unit_filename = create_unit_filename(idx, candidate.title, ".unit.md")
            dafny_filename = create_unit_filename(idx, candidate.title, ".dfy")
            
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
            db.add(unit_file)
            
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
            db.add(dafny_file)
            
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
            db.add(unit_link)
            
            # Commit to database
            db.commit()
            
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
            
            created_links.append(UnitLinkInfo(
                link_id=link_id,
                unit_file_id=unit_file_id,
                dafny_file_id=dafny_file_id,
                source_file_id=str(source_file.file_id),
                link_type="unit-implementation",
                title=candidate.title,
                source_range={
                    "start_line": candidate.line_range[0],
                    "end_line": candidate.line_range[1]
                },
                verification_status="unknown",
                created_at=datetime.utcnow().isoformat()
            ))
            
            successful_count += 1
            
        except Exception as e:
            errors.append(f"Unit '{candidate.title}': {str(e)}")
            failed_count += 1
            db.rollback()
            continue
    
    # Calculate statistics
    end_time = time.time()
    statistics = DeconstructStats(
        total_units=len(unit_candidates),
        successful_units=successful_count,
        failed_units=failed_count,
        total_files_created=successful_count * 2,  # unit.md + .dfy
        processing_time_seconds=round(end_time - start_time, 2)
    )
    
    return DeconstructResponse(
        units=created_units,
        links=created_links,
        statistics=statistics,
        errors=errors
    )


@router.get("/files/{file_id}/traceability", response_model=TraceabilityResponse)
async def get_file_traceability(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    db: Session = Depends(get_db)
):
    """
    Get traceability links for a specification file.
    
    Returns all unit links associated with the root specification file,
    including line ranges for badge positioning in the UI.
    """
    api_key_hash_value = hash_api_key(api_key)
    
    # Verify file exists and ownership
    source_file = db.query(DBFile).filter(
        DBFile.file_id == file_id
    ).first()
    
    if not source_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Query unit links
    unit_links = db.query(DBUnitLink).filter(
        DBUnitLink.root_file_id == file_id
    ).all()
    
    # Format response
    links = []
    for link in unit_links:
        links.append(TraceabilityLink(
            unit_id=str(link.unit_file_id),
            dafny_file_id=str(link.dafny_file_id),
            title=link.title or "Untitled Unit",
            source_range={
                "start_line": link.start_line,
                "end_line": link.end_line
            },
            status=link.verification_status or "unknown"
        ))
    
    return TraceabilityResponse(
        source_file_id=file_id,
        links=links
    )
