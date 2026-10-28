"""
Runtime Verification API Routes

Endpoints for Horizon C: Runtime Verification Pipeline
- Generate tests from Dafny specifications
- Run generated tests
- Extract and compare call graphs
- Ensure Shell (Python) obeys Kernel (Dafny)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import uuid as uuid_lib
import logging
import os
import tempfile
import subprocess

from api.database import get_db, Blueprint as DBBlueprint, File as DBFile
from api.auth import get_current_user
from api.files import get_api_key_from_header
from api.services.test_generator import TestGenerator, TestType
from api.services.call_graph_analyzer import (
    CallGraphAnalyzer
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runtime", tags=["runtime-verification"])


# Request/Response Models
class GenerateTestsRequest(BaseModel):
    """Request to generate tests from Dafny spec"""
    blueprint_id: str = Field(..., description="Blueprint ID")
    component_name: Optional[str] = Field(None, description="Specific component (or None for all)")
    test_types: List[str] = Field(
        default=["unit", "property"],
        description="Test types to generate: 'unit', 'property', 'fuzzer'"
    )


class GeneratedTestResponse(BaseModel):
    """Response model for a generated test"""
    test_name: str
    test_type: str
    test_code: str
    description: str
    method_under_test: str


class GenerateTestsResponse(BaseModel):
    """Response from test generation"""
    success: bool
    blueprint_id: str
    component_name: Optional[str]
    tests: List[GeneratedTestResponse]
    test_module: Optional[str]  # Complete pytest module
    error_message: Optional[str]


class RunTestsRequest(BaseModel):
    """Request to run generated tests"""
    test_code: str = Field(..., description="Pytest test code to execute")
    timeout_seconds: int = Field(30, description="Test execution timeout")


class TestResult(BaseModel):
    """Individual test result"""
    test_name: str
    passed: bool
    duration_ms: float
    output: str


class RunTestsResponse(BaseModel):
    """Response from test execution"""
    success: bool
    total_tests: int
    passed: int
    failed: int
    duration_ms: float
    results: List[TestResult]
    error_message: Optional[str]


class ExtractCallGraphRequest(BaseModel):
    """Request to extract call graph"""
    source_type: str = Field(..., description="'python' or 'mermaid'")
    source_code: str = Field(..., description="Source code or diagram")


class CallGraphNodeResponse(BaseModel):
    """Response model for call graph node"""
    name: str
    calls: List[str]
    called_by: List[str]


class CallGraphResponse(BaseModel):
    """Response with extracted call graph"""
    success: bool
    nodes: Dict[str, CallGraphNodeResponse]
    total_functions: int
    total_calls: int
    error_message: Optional[str]


class CompareCallGraphsRequest(BaseModel):
    """Request to compare expected vs actual call graphs"""
    blueprint_id: str = Field(..., description="Blueprint ID")
    component_name: Optional[str] = Field(None, description="Component name (or None for main)")
    python_code: str = Field(..., description="Python implementation code")


class GraphDiscrepancyResponse(BaseModel):
    """Response model for graph discrepancy"""
    discrepancy_type: str
    source: Optional[str]
    target: Optional[str]
    function_name: Optional[str]
    description: str
    severity: str


class CompareCallGraphsResponse(BaseModel):
    """Response from call graph comparison"""
    success: bool
    similarity_score: float
    total_expected_calls: int
    total_actual_calls: int
    matching_calls: int
    discrepancies: List[GraphDiscrepancyResponse]
    meets_threshold: bool  # True if similarity >= 80%
    error_message: Optional[str]


@router.post("/generate-tests", response_model=GenerateTestsResponse)
async def generate_tests(
    request: GenerateTestsRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate test suite from Dafny specification

    Parses Dafny formal spec and generates:
    - Unit tests for each method
    - Property-based tests using Hypothesis
    - Fuzz tests for robustness
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

        # Find Dafny file
        if request.component_name:
            # Component-specific Dafny
            dafny_file = db.query(DBFile).filter(
                DBFile.blueprint_id == blueprint_uuid,
                DBFile.filename == "core.dfy",
                DBFile.parent_path.like(f"%{request.component_name}%")
            ).first()
        else:
            # Main Dafny file
            dafny_file = db.query(DBFile).filter(
                DBFile.blueprint_id == blueprint_uuid,
                DBFile.filename == "core.dfy",
                DBFile.parent_path.is_(None)
            ).first()

        if not dafny_file:
            raise HTTPException(
                status_code=404,
                detail=f"Dafny file not found for component: {request.component_name or 'main'}"
            )

        # Convert test types
        test_types = []
        for test_type_str in request.test_types:
            if test_type_str == "unit":
                test_types.append(TestType.UNIT)
            elif test_type_str == "property":
                test_types.append(TestType.PROPERTY)
            elif test_type_str == "fuzzer":
                test_types.append(TestType.FUZZER)

        # Generate tests
        generator = TestGenerator()
        tests = generator.generate_from_dafny(dafny_file.content, test_types)

        # Create full test module
        test_module = generator.create_test_module(
            tests,
            component_name=request.component_name or "main"
        )

        # Convert to response format
        tests_response = [
            GeneratedTestResponse(
                test_name=test.test_name,
                test_type=test.test_type.value,
                test_code=test.test_code,
                description=test.description,
                method_under_test=test.method_under_test
            )
            for test in tests
        ]

        logger.info(
            f"Generated {len(tests)} tests for blueprint {request.blueprint_id}, "
            f"component: {request.component_name or 'main'}"
        )

        return GenerateTestsResponse(
            success=True,
            blueprint_id=request.blueprint_id,
            component_name=request.component_name,
            tests=tests_response,
            test_module=test_module,
            error_message=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate tests: {e}")
        return GenerateTestsResponse(
            success=False,
            blueprint_id=request.blueprint_id,
            component_name=request.component_name,
            tests=[],
            test_module=None,
            error_message=str(e)
        )


@router.post("/run-tests", response_model=RunTestsResponse)
async def run_tests(
    request: RunTestsRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Execute generated test suite

    Runs pytest tests in a sandboxed environment and returns results.
    """
    try:
        # Create temporary file for test code
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False
        ) as f:
            f.write(request.test_code)
            test_file = f.name

        try:
            # Run pytest with timeout
            result = subprocess.run(
                ['pytest', test_file, '-v', '--tb=short', '--json-report'],
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds
            )

            # Parse pytest output
            # This is a simplified parser - in production, use pytest-json-report plugin
            output_lines = result.stdout.split('\n')
            test_results = []
            passed = 0
            failed = 0

            for line in output_lines:
                if 'PASSED' in line:
                    passed += 1
                    test_name = line.split('::')[1].split()[0] if '::' in line else 'unknown'
                    test_results.append(TestResult(
                        test_name=test_name,
                        passed=True,
                        duration_ms=0.0,
                        output=line
                    ))
                elif 'FAILED' in line:
                    failed += 1
                    test_name = line.split('::')[1].split()[0] if '::' in line else 'unknown'
                    test_results.append(TestResult(
                        test_name=test_name,
                        passed=False,
                        duration_ms=0.0,
                        output=line
                    ))

            total_tests = passed + failed

            logger.info(f"Test execution: {passed}/{total_tests} passed")

            return RunTestsResponse(
                success=True,
                total_tests=total_tests,
                passed=passed,
                failed=failed,
                duration_ms=0.0,  # TODO: Extract from pytest output
                results=test_results,
                error_message=None
            )

        finally:
            # Clean up temp file
            if os.path.exists(test_file):
                os.unlink(test_file)

    except subprocess.TimeoutExpired:
        logger.error(f"Test execution timed out after {request.timeout_seconds}s")
        return RunTestsResponse(
            success=False,
            total_tests=0,
            passed=0,
            failed=0,
            duration_ms=0.0,
            results=[],
            error_message=f"Test execution timed out after {request.timeout_seconds}s"
        )
    except Exception as e:
        logger.error(f"Failed to run tests: {e}")
        return RunTestsResponse(
            success=False,
            total_tests=0,
            passed=0,
            failed=0,
            duration_ms=0.0,
            results=[],
            error_message=str(e)
        )


@router.post("/call-graph", response_model=CallGraphResponse)
async def extract_call_graph(
    request: ExtractCallGraphRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user)
):
    """
    Extract call graph from source code or diagram

    Supports:
    - Python code (AST-based extraction)
    - Mermaid diagrams (flowchart and sequence)
    """
    try:
        analyzer = CallGraphAnalyzer()

        if request.source_type == "python":
            graph = analyzer.extract_from_python(request.source_code)
        elif request.source_type == "mermaid":
            graph = analyzer.extract_from_mermaid(request.source_code)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source_type: {request.source_type}. Must be 'python' or 'mermaid'"
            )

        # Convert to response format
        nodes_response = {}
        for name, node in graph.nodes.items():
            nodes_response[name] = CallGraphNodeResponse(
                name=node.name,
                calls=list(node.calls),
                called_by=list(node.called_by)
            )

        total_calls = len(graph.get_all_calls())

        logger.info(
            f"Extracted call graph from {request.source_type}: "
            f"{len(graph.nodes)} functions, {total_calls} calls"
        )

        return CallGraphResponse(
            success=True,
            nodes=nodes_response,
            total_functions=len(graph.nodes),
            total_calls=total_calls,
            error_message=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to extract call graph: {e}")
        return CallGraphResponse(
            success=False,
            nodes={},
            total_functions=0,
            total_calls=0,
            error_message=str(e)
        )


@router.post("/compare", response_model=CompareCallGraphsResponse)
async def compare_call_graphs(
    request: CompareCallGraphsRequest,
    api_key: str = Depends(get_api_key_from_header),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare expected (Mermaid) vs actual (Python) call graphs

    Verifies that Python implementation matches the architectural
    design specified in the Mermaid diagram.

    Similarity score >= 80% indicates acceptable compliance.
    """
    try:
        # Convert blueprint_id to UUID
        try:
            blueprint_uuid = uuid_lib.UUID(request.blueprint_id)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid blueprint ID format")

        # Find Mermaid diagram
        if request.component_name:
            # Component diagram
            diagram_file = db.query(DBFile).filter(
                DBFile.blueprint_id == blueprint_uuid,
                DBFile.filename == "diagram.mmd",
                DBFile.parent_path.like(f"%{request.component_name}%")
            ).first()
        else:
            # Main diagram
            diagram_file = db.query(DBFile).filter(
                DBFile.blueprint_id == blueprint_uuid,
                DBFile.filename == "diagram.mmd",
                DBFile.parent_path.is_(None)
            ).first()

        if not diagram_file:
            raise HTTPException(
                status_code=404,
                detail=f"Mermaid diagram not found for component: {request.component_name or 'main'}"
            )

        # Extract and compare graphs
        analyzer = CallGraphAnalyzer()
        expected_graph = analyzer.extract_from_mermaid(diagram_file.content)
        actual_graph = analyzer.extract_from_python(request.python_code)

        comparison = analyzer.compare_graphs(expected_graph, actual_graph)

        # Convert discrepancies to response format
        discrepancies_response = [
            GraphDiscrepancyResponse(
                discrepancy_type=d.discrepancy_type.value,
                source=d.source,
                target=d.target,
                function_name=d.function_name,
                description=d.description,
                severity=d.severity
            )
            for d in comparison.discrepancies
        ]

        meets_threshold = comparison.similarity_score >= 80.0

        logger.info(
            f"Call graph comparison: {comparison.similarity_score}% similarity, "
            f"{len(comparison.discrepancies)} discrepancies"
        )

        return CompareCallGraphsResponse(
            success=True,
            similarity_score=comparison.similarity_score,
            total_expected_calls=comparison.total_expected_calls,
            total_actual_calls=comparison.total_actual_calls,
            matching_calls=comparison.matching_calls,
            discrepancies=discrepancies_response,
            meets_threshold=meets_threshold,
            error_message=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare call graphs: {e}")
        return CompareCallGraphsResponse(
            success=False,
            similarity_score=0.0,
            total_expected_calls=0,
            total_actual_calls=0,
            matching_calls=0,
            discrepancies=[],
            meets_threshold=False,
            error_message=str(e)
        )
