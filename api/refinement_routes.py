"""
Component Refinement API Routes

Endpoints for analyzing blueprint complexity and enforcing
the 4+ component architectural standard.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import uuid as uuid_lib
import logging

from api.database import get_db, Blueprint as DBBlueprint, File as DBFile
from api.auth import get_current_user
from api.files import get_api_key_from_header
from api.services.refinement_service import (
    RefinementService,
    ComponentCategory
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/refinement", tags=["component-refinement"])


# Request/Response Models
class ComponentSuggestionResponse(BaseModel):
    """Response model for component suggestion"""
    suggested_name: str
    category: str
    description: str
    estimated_size: int
    key_requirements: List[str]


class ComplexityReportResponse(BaseModel):
    """Response model for complexity report"""
    blueprint_id: str
    total_lines: int
    component_count: int
    meets_minimum: bool
    complexity_score: float
    size_distribution: Dict[str, int]
    recommendations: List[str]
    component_suggestions: List[ComponentSuggestionResponse]


class AutoRefineRequest(BaseModel):
    """Request to auto-refine a blueprint"""
    blueprint_id: str = Field(..., description="Blueprint ID to refine")
    target_components: int = Field(4, description="Target number of components")


class AutoRefineResponse(BaseModel):
    """Response from auto-refinement"""
    success: bool
    refined_components: List[Dict]
    error_message: Optional[str]
    message: str


class EnforceMetricRequest(BaseModel):
    """Request to check if blueprint meets metric"""
    blueprint_id: str = Field(..., description="Blueprint ID to check")


class EnforceMetricResponse(BaseModel):
    """Response from metric enforcement"""
    blueprint_id: str
    passes_metric: bool
    component_count: int
    minimum_required: int
    error_message: Optional[str]
    suggestions: List[ComponentSuggestionResponse]


@router.get("/complexity/{blueprint_id}", response_model=ComplexityReportResponse)
async def get_complexity_report(
    blueprint_id: str,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complexity analysis for a blueprint

    Analyzes:
    - Total lines of spec
    - Component count
    - Whether it meets the 4+ component minimum
    - Complexity score
    - Size distribution
    - Recommendations for improvement
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_uuid = uuid_lib.UUID(blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Get all files for this blueprint
        files = db.query(DBFile).filter(
            DBFile.blueprint_id == blueprint_uuid
        ).all()

        # Count components (folders with spec.md and core.dfy)
        components = {}
        main_spec_content = ""

        for file in files:
            if file.filename == "spec.md" and not file.parent_path:
                # Main spec
                main_spec_content = file.content
            elif file.filename == "spec.md" and file.parent_path:
                # Component spec
                component_name = file.parent_path.split('/')[-1]
                components[component_name] = len(file.content.split('\n'))

        component_count = len(components)

        # If no components found, count as 1 (monolithic)
        if component_count == 0 and main_spec_content:
            component_count = 1
            components = {"Main": len(main_spec_content.split('\n'))}

        # Analyze complexity
        refinement_service = RefinementService()
        report = refinement_service.analyze_complexity(
            main_spec_content,
            component_count,
            components
        )

        # Convert to response model
        suggestions_response = [
            ComponentSuggestionResponse(
                suggested_name=s.suggested_name,
                category=s.category.value,
                description=s.description,
                estimated_size=s.estimated_size,
                key_requirements=s.key_requirements
            )
            for s in report.component_suggestions
        ]

        logger.info(
            f"Complexity report for blueprint {blueprint_id}: "
            f"{component_count} components, meets minimum: {report.meets_minimum}"
        )

        return ComplexityReportResponse(
            blueprint_id=blueprint_id,
            total_lines=report.total_lines,
            component_count=report.component_count,
            meets_minimum=report.meets_minimum,
            complexity_score=report.complexity_score,
            size_distribution=report.size_distribution,
            recommendations=report.recommendations,
            component_suggestions=suggestions_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate complexity report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auto-refine", response_model=AutoRefineResponse)
async def auto_refine_blueprint(
    request: AutoRefineRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto-refine a blueprint to have more components

    Uses AI to analyze the spec and suggest how to decompose it
    into the target number of components.
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_uuid = uuid_lib.UUID(request.blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Get main spec
        main_spec = db.query(DBFile).filter(
            DBFile.blueprint_id == blueprint_uuid,
            DBFile.filename == "spec.md",
            DBFile.parent_path.is_(None)
        ).first()

        if not main_spec:
            raise HTTPException(status_code=404, detail="Main spec not found")

        # Auto-refine
        refinement_service = RefinementService()
        success, components, error = refinement_service.auto_refine_spec(
            main_spec.content,
            request.target_components
        )

        if success:
            message = f"Successfully generated {len(components)} component suggestions"
        else:
            message = f"Failed to auto-refine: {error}"

        logger.info(f"Auto-refine for blueprint {request.blueprint_id}: {message}")

        return AutoRefineResponse(
            success=success,
            refined_components=components,
            error_message=error,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to auto-refine blueprint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enforce-metric", response_model=EnforceMetricResponse)
async def enforce_component_metric(
    request: EnforceMetricRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if a blueprint meets the minimum component requirement

    Returns whether the blueprint passes the 4+ component metric,
    and provides suggestions if it doesn't.
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_uuid = uuid_lib.UUID(request.blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Load blueprint
        blueprint = db.query(DBBlueprint).filter(
            DBBlueprint.blueprint_id == blueprint_uuid
        ).first()

        if not blueprint:
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Get main spec
        main_spec = db.query(DBFile).filter(
            DBFile.blueprint_id == blueprint_uuid,
            DBFile.filename == "spec.md",
            DBFile.parent_path.is_(None)
        ).first()

        if not main_spec:
            raise HTTPException(status_code=404, detail="Main spec not found")

        # Count components
        files = db.query(DBFile).filter(
            DBFile.blueprint_id == blueprint_uuid
        ).all()

        component_count = 0
        for file in files:
            if file.filename == "spec.md" and file.parent_path:
                component_count += 1

        # If no component structure, count as 1
        if component_count == 0:
            component_count = 1

        # Enforce metric
        refinement_service = RefinementService()
        passes, error_message, suggestions = refinement_service.enforce_metric(
            main_spec.content,
            component_count
        )

        # Convert suggestions to response model
        suggestions_response = [
            ComponentSuggestionResponse(
                suggested_name=s.suggested_name,
                category=s.category.value,
                description=s.description,
                estimated_size=s.estimated_size,
                key_requirements=s.key_requirements
            )
            for s in suggestions
        ]

        logger.info(
            f"Metric enforcement for blueprint {request.blueprint_id}: "
            f"passes={passes}, component_count={component_count}"
        )

        return EnforceMetricResponse(
            blueprint_id=request.blueprint_id,
            passes_metric=passes,
            component_count=component_count,
            minimum_required=refinement_service.MINIMUM_COMPONENTS,
            error_message=error_message,
            suggestions=suggestions_response
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to enforce metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categorize/{blueprint_id}/{component_name}")
async def categorize_component(
    blueprint_id: str,
    component_name: str,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Categorize a component based on its specification

    Returns the component category:
    - StateContainer: Data structures and invariants
    - TransitionLogic: Workflows and business logic
    - AccessControl: Authentication and authorization
    - DataValidator: Input validation and constraints
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_uuid = uuid_lib.UUID(blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Find component spec
        component_spec = db.query(DBFile).filter(
            DBFile.blueprint_id == blueprint_uuid,
            DBFile.filename == "spec.md",
            DBFile.parent_path.like(f"%{component_name}%")
        ).first()

        if not component_spec:
            raise HTTPException(status_code=404, detail="Component spec not found")

        # Categorize
        refinement_service = RefinementService()
        category = refinement_service.categorize_component(
            component_name,
            component_spec.content
        )

        return {
            "blueprint_id": blueprint_id,
            "component_name": component_name,
            "category": category.value,
            "description": _get_category_description(category)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to categorize component: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_category_description(category: ComponentCategory) -> str:
    """Get human-readable description of category"""
    descriptions = {
        ComponentCategory.STATE_CONTAINER: "Data structures, state, and invariants",
        ComponentCategory.TRANSITION_LOGIC: "Business logic and workflows",
        ComponentCategory.ACCESS_CONTROL: "Authentication and authorization",
        ComponentCategory.DATA_VALIDATOR: "Input validation and constraints",
        ComponentCategory.GENERAL: "General purpose component"
    }
    return descriptions.get(category, "Unknown category")
