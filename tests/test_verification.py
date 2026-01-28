"""
Integration tests for Verification API endpoints
Smoke tests to ensure endpoints exist and accept requests.
Mocks Dafny execution to verify the controller, not the tool.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.models import VerifyResponse, VerificationResult, VerificationError


def test_verify_dafny_endpoint_structure(client, headers):
    """
    Smoke test: Ensure /api/verify endpoint exists and accepts valid payload.
    Mocks the subprocess.run call to avoid needing Dafny/Z3 installed.
    """
    # Mock subprocess.run to simulate successful Dafny verification
    mock_subprocess_result = MagicMock()
    mock_subprocess_result.returncode = 0
    mock_subprocess_result.stdout = "Dafny program verifier finished with 1 verified, 0 errors"
    mock_subprocess_result.stderr = ""
    
    # Mock shutil.which to return a path (Dafny is "available")
    # Note: shutil is imported inside the function, so we patch it at the function level
    import shutil
    import subprocess
    import tempfile
    
    with patch.object(shutil, "which", return_value="/usr/bin/dafny"), \
         patch.object(subprocess, "run", return_value=mock_subprocess_result), \
         patch.object(tempfile, "NamedTemporaryFile") as mock_temp:
        
        # Mock tempfile to return a file path
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.dfy"
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=None)
        mock_temp.return_value = mock_file
        
        response = client.post(
            "/api/verify",
            json={
                "dafny_code": "method Main() {}",
                "solver": "z3",
                "timeout_seconds": 10,
                "verbosity": "normal"
            },
            headers=headers
        )
        
        # Should succeed (200) because we mocked the internal runner
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "verified" in data
        assert "verification_time_ms" in data
        assert "errors" in data
        assert "results" in data


def test_verify_dafny_missing_dafny(client, headers):
    """
    Test that endpoint returns 503 when Dafny is not available.
    """
    import shutil
    with patch.object(shutil, "which", return_value=None):
        response = client.post(
            "/api/verify",
            json={
                "dafny_code": "method Main() {}",
                "solver": "z3",
                "timeout_seconds": 10
            },
            headers=headers
        )
        
        assert response.status_code == 503
        assert "Dafny verifier not available" in response.json()["detail"]


def test_verify_dafny_invalid_request(client, headers):
    """
    Test that endpoint validates request structure.
    """
    # Missing required field
    response = client.post(
        "/api/verify",
        json={
            "solver": "z3"
            # Missing dafny_code
        },
        headers=headers
    )
    
    # Should return 422 (validation error)
    assert response.status_code == 422


def test_verify_dafny_timeout(client, headers):
    """
    Test that endpoint handles timeout gracefully.
    """
    from subprocess import TimeoutExpired
    
    import shutil
    from subprocess import TimeoutExpired
    with patch("shutil.which", return_value="/usr/bin/dafny"), \
         patch("subprocess.run", side_effect=TimeoutExpired("dafny", 10)), \
         patch("tempfile.NamedTemporaryFile") as mock_temp:
        
        mock_file = MagicMock()
        mock_file.name = "/tmp/test.dfy"
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=None)
        mock_temp.return_value = mock_file
        
        response = client.post(
            "/api/verify",
            json={
                "dafny_code": "method Main() {}",
                "solver": "z3",
                "timeout_seconds": 10
            },
            headers=headers
        )
        
        assert response.status_code == 408
        assert "timeout" in response.json()["detail"].lower()
