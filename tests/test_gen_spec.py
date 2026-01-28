"""
Integration tests for Spec Generation API endpoints
Smoke tests to ensure endpoints exist and accept requests.
Mocks the SpecGeneratorService to avoid Gemini API calls.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.models import (
    GenerateSpecResponse,
    FindGapsResponse,
    RefineSpecResponse,
    SpecStatistics,
    Gap,
    GapLocation
)


def test_generate_spec_endpoint_structure(client, headers, db_session):
    """
    Smoke test: Ensure /api/generate/spec endpoint works.
    Mocks the SpecGeneratorService to avoid Gemini calls.
    """
    mock_spec_response = GenerateSpecResponse(
        triage={"doc_type": "requirements", "confidence": 0.9, "detected_patterns": []},
        structured_spec="# Specification\n\nCreate a bank account system.",
        dafny_skeleton="method Main() {\n    // Bank account system\n}",
        gaps=[],
        ambiguities=[],
        traceability_matrix=[],
        statistics=SpecStatistics(
            total_requirements=1,
            mapped_requirements=1,
            coverage_percentage=100.0,
            total_gaps=0,
            critical_gaps=0
        ),
        suggested_filename=None,
        units_created=None,
        subfolder_name=None
    )
    
    # Patch the SpecGeneratorService.generate_spec method
    with patch("api.services.spec_generator.SpecGeneratorService.generate_spec", return_value=mock_spec_response):
        response = client.post(
            "/api/generate/spec",
            json={
                "english_spec": "Create a bank account system.",
                "project_id": None,
                "source_file_id": None,
                "options": {
                    "include_examples": False,
                    "strictness_level": "medium",
                    "target_language": "dafny"
                }
            },
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "dafny_skeleton" in data
        assert "structured_spec" in data
        assert "triage" in data
        assert "statistics" in data


def test_find_gaps_endpoint_structure(client, headers):
    """
    Smoke test: Ensure /api/generate/find-gaps endpoint works.
    """
    mock_gaps_response = FindGapsResponse(
        gaps=[
            Gap(
                id="gap-1",
                severity="high",
                category="missing-precondition",
                description="Missing precondition check",
                location=GapLocation(line=10, column=5, file="spec.md"),
                suggestion="Add precondition check",
                code_snippet=None
            )
        ],
        ambiguities=[],
        statistics=SpecStatistics(
            total_requirements=1,
            mapped_requirements=1,
            coverage_percentage=100.0,
            total_gaps=1,
            critical_gaps=0
        )
    )
    
    # Patch the SpecGeneratorService.find_gaps method
    with patch("api.services.spec_generator.SpecGeneratorService.find_gaps", return_value=mock_gaps_response):
        response = client.post(
            "/api/generate/find-gaps",
            json={
                "spec": "# Specification\n\nCreate a bank account system.",
                "project_id": None,
                "source_file_id": None
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "gaps" in data
        assert "ambiguities" in data
        assert "statistics" in data


def test_refine_spec_endpoint_structure(client, headers):
    """
    Smoke test: Ensure /api/generate/refine-spec endpoint works.
    """
    mock_refine_response = RefineSpecResponse(
        refined_spec="# Refined Specification\n\nCreate a bank account system with proper preconditions.",
        applied_gaps=[
            Gap(
                id="gap-1",
                severity="high",
                category="missing-precondition",
                description="Missing precondition check",
                location=GapLocation(line=10, column=5, file="spec.md"),
                suggestion="Add precondition check",
                code_snippet=None
            )
        ]
    )
    
    # Patch the SpecGeneratorService.refine_spec method
    with patch("api.services.spec_generator.SpecGeneratorService.refine_spec", return_value=mock_refine_response):
        response = client.post(
            "/api/generate/refine-spec",
            json={
                "spec": "# Specification\n\nCreate a bank account system.",
                "gaps": [
                    {
                        "id": "gap-1",
                        "severity": "high",
                        "category": "missing-precondition",
                        "description": "Missing precondition check",
                        "location": {"line": 10, "column": 5, "file": "spec.md"},
                        "suggestion": "Add precondition check"
                    }
                ],
                "apply_gap_ids": ["gap-1"]
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "refined_spec" in data
        assert "applied_gaps" in data


def test_generate_spec_invalid_request(client, headers):
    """
    Test that endpoint validates request structure.
    """
    # Missing required field
    response = client.post(
        "/api/generate/spec",
        json={
            "project_id": None
            # Missing english_spec
        },
        headers=headers
    )
    
    # Should return 422 (validation error)
    assert response.status_code == 422
