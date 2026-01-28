"""
Integration tests for Authentication API endpoints
Smoke tests to ensure endpoints are routed correctly and handle requests.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


def test_auth_github_endpoint_existence(client, monkeypatch):
    """
    Smoke test: Ensure /api/auth/github endpoint exists and returns authorization URL.
    """
    # Patch the module-level variables directly since they're read at import time
    import api.auth
    monkeypatch.setattr(api.auth, "GITHUB_CLIENT_ID", "test_client_id")
    monkeypatch.setattr(api.auth, "FRONTEND_URL", "http://localhost:3000")
    
    response = client.get("/api/auth/github", follow_redirects=False)
    
    # Should return 200 with authorization_url (not redirect, returns JSON)
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "github.com/login/oauth/authorize" in data["authorization_url"]


def test_auth_github_missing_config(client, monkeypatch):
    """
    Test that endpoint returns 500 when GitHub OAuth is not configured.
    """
    # Patch the module-level variable directly since it's read at import time
    import api.auth
    monkeypatch.setattr(api.auth, "GITHUB_CLIENT_ID", "")
    
    response = client.get("/api/auth/github", follow_redirects=False)
    
    # Should return 500 with error message
    assert response.status_code == 500
    assert "not configured" in response.json()["detail"].lower()


def test_auth_logout_endpoint(client):
    """
    Smoke test: Ensure /api/auth/logout endpoint exists.
    Logout should work without authentication (clears cookies).
    """
    response = client.post("/api/auth/logout")
    
    # Should return 200 (successfully clears cookies)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"


def test_auth_refresh_endpoint_structure(client):
    """
    Smoke test: Ensure /api/auth/refresh endpoint exists.
    Without a refresh token cookie, should return 401.
    """
    response = client.post("/api/auth/refresh")
    
    # Should return 401 (no refresh token provided)
    assert response.status_code == 401
    assert "No refresh token" in response.json()["detail"] or "refresh token" in response.json()["detail"].lower()


def test_auth_me_endpoint_requires_auth(client):
    """
    Smoke test: Ensure /api/auth/me endpoint requires authentication.
    """
    response = client.get("/api/auth/me")
    
    # Should return 401 (authentication required)
    assert response.status_code == 401
    assert "required" in response.json()["detail"].lower() or "authentication" in response.json()["detail"].lower()


def test_auth_github_callback_missing_code(client, monkeypatch):
    """
    Test that /api/auth/github/callback handles missing code parameter.
    """
    # Patch the module-level variables directly since they're read at import time
    import api.auth
    monkeypatch.setattr(api.auth, "GITHUB_CLIENT_ID", "test_client_id")
    monkeypatch.setattr(api.auth, "FRONTEND_URL", "http://localhost:3000")
    
    response = client.get("/api/auth/github/callback", follow_redirects=False)
    
    # Should redirect to frontend with error
    assert response.status_code in [302, 307, 200]  # Redirect or JSON response
    # If redirect, check location header
    if response.status_code in [302, 307]:
        assert "error" in response.headers.get("location", "").lower() or "auth=error" in response.headers.get("location", "")


def test_auth_github_callback_with_code(client, monkeypatch):
    """
    Test that /api/auth/github/callback handles code parameter (mocked).
    """
    # Patch the module-level variables directly since they're read at import time
    import api.auth
    monkeypatch.setattr(api.auth, "GITHUB_CLIENT_ID", "test_client_id")
    monkeypatch.setattr(api.auth, "GITHUB_CLIENT_SECRET", "test_secret")
    monkeypatch.setattr(api.auth, "FRONTEND_URL", "http://localhost:3000")
    
    # Mock the GitHub OAuth token exchange and user info responses
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {"access_token": "test_token"}
    
    mock_user_response = MagicMock()
    mock_user_response.status_code = 200
    mock_user_response.json.return_value = {
        "id": 12345,
        "login": "testuser",
        "email": "test@example.com",
        "avatar_url": "https://example.com/avatar.png"
    }
    
    # Create a proper async context manager mock
    class MockAsyncClient:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            return None
        
        async def post(self, *args, **kwargs):
            return mock_token_response
        
        async def get(self, *args, **kwargs):
            return mock_user_response
    
    # Mock AsyncClient class to return our mock
    with patch("api.auth.httpx.AsyncClient", MockAsyncClient):
        response = client.get(
            "/api/auth/github/callback?code=test_code&state=test_state",
            follow_redirects=False
        )
        
        # Should redirect to frontend with success or return JSON
        assert response.status_code in [200, 302, 307]
