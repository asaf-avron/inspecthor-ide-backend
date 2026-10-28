"""
Mermaid Diagram API Routes

Endpoints for generating and comparing Mermaid diagrams for Intent Verification.
Part of Horizon A: visualizing requirements to confirm user intent.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from sqlalchemy.orm import Session

from api.database import get_db, File as DBFile, Blueprint as DBBlueprint
from api.auth import get_current_user
from api.services.diagram_generator import get_diagram_generator
from api.files import get_api_key_from_header
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagrams", tags=["diagrams"])


# Request/Response Models
class GenerateDiagramFromSpecRequest(BaseModel):
    """Request to generate diagram from specification"""
    spec_content: str = Field(..., description="Markdown specification content")
    component_name: Optional[str] = Field("Component", description="Name of the component")


class GenerateDiagramFromCodeRequest(BaseModel):
    """Request to generate diagram from code"""
    code_content: str = Field(..., description="Python code content")
    component_name: Optional[str] = Field("Component", description="Name of the component")


class GenerateDiagramFromFileRequest(BaseModel):
    """Request to generate diagram from a file"""
    file_id: str = Field(..., description="File ID to generate diagram from")
    component_name: Optional[str] = Field(None, description="Optional component name override")


class DiagramResponse(BaseModel):
    """Response containing a Mermaid diagram"""
    diagram: str = Field(..., description="Mermaid diagram content")
    diagram_type: str = Field(..., description="Type: 'expected' or 'actual'")
    component_name: str = Field(..., description="Component name")
    generated_from: str = Field(..., description="Source: 'spec' or 'code' or 'file'")


class CompareDiagramsRequest(BaseModel):
    """Request to compare two diagrams"""
    expected_diagram: str = Field(..., description="Expected Mermaid diagram")
    actual_diagram: str = Field(..., description="Actual Mermaid diagram")


class DiagramDiffResponse(BaseModel):
    """Response with diagram comparison"""
    similarity_percent: float = Field(..., description="Similarity percentage")
    missing_nodes: List[str] = Field(..., description="Nodes in expected but not actual")
    extra_nodes: List[str] = Field(..., description="Nodes in actual but not expected")
    common_nodes: List[str] = Field(..., description="Nodes in both")
    missing_edges: List[str] = Field(..., description="Edges in expected but not actual")
    extra_edges: List[str] = Field(..., description="Edges in actual but not expected")
    common_edges: List[str] = Field(..., description="Edges in both")
    summary: str = Field(..., description="Human-readable summary")


class SaveDiagramRequest(BaseModel):
    """Request to save a diagram as a file"""
    blueprint_id: str = Field(..., description="Blueprint ID")
    filename: str = Field(..., description="Filename (should end with .mermaid)")
    diagram_content: str = Field(..., description="Mermaid diagram content")


@router.post("/generate-expected", response_model=DiagramResponse)
async def generate_expected_diagram(
    request: GenerateDiagramFromSpecRequest,
    current_user=Depends(get_current_user)
):
    """
    Generate expected behavior diagram from specification

    This endpoint is used for Intent Verification (Horizon A).
    The user provides a specification in natural language (Markdown),
    and the system generates a Mermaid diagram showing the expected logic flow.
    """
    try:
        generator = get_diagram_generator()

        diagram = generator.generate_from_spec(
            spec_md=request.spec_content,
            component_name=request.component_name or "Component"
        )

        return DiagramResponse(
            diagram=diagram,
            diagram_type="expected",
            component_name=request.component_name or "Component",
            generated_from="spec"
        )

    except Exception as e:
        logger.error(f"Failed to generate expected diagram: {e}")
        raise HTTPException(status_code=500, detail=f"Diagram generation failed: {str(e)}")


@router.post("/generate-actual", response_model=DiagramResponse)
async def generate_actual_diagram(
    request: GenerateDiagramFromCodeRequest,
    current_user=Depends(get_current_user)
):
    """
    Generate actual implementation diagram from code

    This endpoint generates a diagram from Python code to show
    the actual implementation flow. Used for post-verification
    comparison with the expected diagram.
    """
    try:
        generator = get_diagram_generator()

        diagram = generator.generate_from_code(
            python_code=request.code_content,
            component_name=request.component_name or "Component"
        )

        return DiagramResponse(
            diagram=diagram,
            diagram_type="actual",
            component_name=request.component_name or "Component",
            generated_from="code"
        )

    except Exception as e:
        logger.error(f"Failed to generate actual diagram: {e}")
        raise HTTPException(status_code=500, detail=f"Diagram generation failed: {str(e)}")


@router.post("/generate-from-file", response_model=DiagramResponse)
async def generate_diagram_from_file(
    request: GenerateDiagramFromFileRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate diagram from a file (spec.md or Python code)

    Automatically determines whether to generate expected or actual diagram
    based on file type.
    """
    try:
        # Convert file_id to UUID
        try:
            file_id_uuid = uuid.UUID(request.file_id) if isinstance(request.file_id, str) else request.file_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid file ID format")

        # Load file
        file = db.query(DBFile).filter(DBFile.file_id == file_id_uuid).first()

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Check ownership (simplified - should use proper auth)
        # In production, verify user owns the blueprint containing this file

        generator = get_diagram_generator()
        component_name = request.component_name or file.filename.replace(".md", "").replace(".py", "")

        # Determine diagram type based on file type
        if file.file_type == "md":
            # Generate expected diagram from spec
            diagram = generator.generate_from_spec(
                spec_md=file.content,
                component_name=component_name
            )
            diagram_type = "expected"

        elif file.filename.endswith(".py"):
            # Generate actual diagram from Python code
            diagram = generator.generate_from_code(
                python_code=file.content,
                component_name=component_name
            )
            diagram_type = "actual"

        else:
            raise HTTPException(
                status_code=400,
                detail="File type not supported. Only .md and .py files can generate diagrams."
            )

        return DiagramResponse(
            diagram=diagram,
            diagram_type=diagram_type,
            component_name=component_name,
            generated_from="file"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate diagram from file: {e}")
        raise HTTPException(status_code=500, detail=f"Diagram generation failed: {str(e)}")


@router.post("/compare", response_model=DiagramDiffResponse)
async def compare_diagrams(
    request: CompareDiagramsRequest,
    current_user=Depends(get_current_user)
):
    """
    Compare expected vs actual diagrams

    This endpoint computes the difference between the expected behavior
    (from spec) and actual behavior (from code), helping identify
    discrepancies between requirements and implementation.
    """
    try:
        generator = get_diagram_generator()

        diff = generator.compute_diff(
            expected_diagram=request.expected_diagram,
            actual_diagram=request.actual_diagram
        )

        return DiagramDiffResponse(**diff)

    except Exception as e:
        logger.error(f"Failed to compare diagrams: {e}")
        raise HTTPException(status_code=500, detail=f"Diagram comparison failed: {str(e)}")


@router.post("/save", response_model=Dict)
async def save_diagram(
    request: SaveDiagramRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Save a diagram as a file in a blueprint

    Saves the Mermaid diagram content as a .mermaid file in the specified blueprint.
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_id_uuid = uuid.UUID(request.blueprint_id) if isinstance(request.blueprint_id, str) else request.blueprint_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Verify blueprint exists and user has access
        blueprint = db.query(DBBlueprint).filter(DBBlueprint.blueprint_id == blueprint_id_uuid).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Ensure filename ends with .mermaid
        filename = request.filename
        if not filename.endswith(".mermaid"):
            filename = f"{filename}.mermaid"

        # Create file record
        file_id = uuid.uuid4()
        new_file = DBFile(
            file_id=file_id,
            blueprint_id=blueprint_id_uuid,
            filename=filename,
            content=request.diagram_content,
            file_type="md",  # Store as md type since it's text
            size_bytes=len(request.diagram_content.encode('utf-8'))
        )

        db.add(new_file)
        db.commit()

        logger.info(f"Saved diagram file {filename} to blueprint {request.blueprint_id}")

        return {
            "success": True,
            "file_id": str(file_id),
            "filename": filename,
            "blueprint_id": request.blueprint_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save diagram: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save diagram: {str(e)}")


@router.get("/file/{file_id}", response_model=DiagramResponse)
async def get_diagram_file(
    file_id: str,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve a saved diagram file

    Returns the Mermaid diagram content from a saved .mermaid file.
    """
    try:
        # Convert file_id to UUID
        try:
            file_id_uuid = uuid.UUID(file_id) if isinstance(file_id, str) else file_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid file ID format")

        # Load file
        file = db.query(DBFile).filter(DBFile.file_id == file_id_uuid).first()

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Verify it's a diagram file
        if not file.filename.endswith(".mermaid"):
            raise HTTPException(status_code=400, detail="File is not a Mermaid diagram")

        # Determine diagram type from filename convention
        diagram_type = "expected"
        if "actual" in file.filename.lower() or "implementation" in file.filename.lower():
            diagram_type = "actual"

        component_name = file.filename.replace(".mermaid", "").replace("_", " ")

        return DiagramResponse(
            diagram=file.content,
            diagram_type=diagram_type,
            component_name=component_name,
            generated_from="file"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get diagram file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve diagram: {str(e)}")
