"""
Integration tests for Authentication API endpoints
Smoke tests to ensure endpoints are routed correctly and handle requests.

Tests cover:
- OAuth flow endpoints
- JWT token handling
- AuthService integration
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import os


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


def test_auth_me_with_string_uuid_in_token(client, db_session, monkeypatch):
    """
    Test that /api/auth/me handles JWT tokens with string UUIDs correctly.
    This reproduces the SQLite UUID issue where string UUIDs from JWT payloads
    need to be converted to UUID objects before database queries.
    """
    import uuid
    from api.database import User
    
    # Create a test user with required fields
    import api.auth
    dummy_token = api.auth.encrypt_token("dummy_token")
    test_user = User(
        github_id=99999,
        github_login="testuser_uuid",
        email="testuuid@example.com",
        avatar_url="https://example.com/avatar.png",
        access_token_encrypted=dummy_token,
        tier='free',
        verification_credits=10
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)
    
    # Create a JWT token with string UUID (as JWT tokens contain)
    user_id_str = str(test_user.user_id)
    token_data = {
        "sub": user_id_str,  # String UUID, not UUID object
        "github_id": test_user.github_id,
        "github_login": test_user.github_login,
        "tier": test_user.tier,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=15)
    }
    
    # Patch JWT_SECRET for token creation
    monkeypatch.setattr(api.auth, "JWT_SECRET", "test-secret-key")
    
    # Create token using the auth module's function
    access_token = api.auth.create_access_token({
        "sub": user_id_str,
        "github_id": test_user.github_id,
        "github_login": test_user.github_login,
        "tier": test_user.tier,
    })
    
    # Make request with the token cookie
    response = client.get(
        "/api/auth/me",
        cookies={"access_token": access_token}
    )
    
    # Should succeed and return user info (after fix)
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id_str
    assert data["github_login"] == "testuser_uuid"


# ============================================================
# AuthService Tests
# ============================================================

class TestAuthService:
    """Tests for the AuthService class (Imperative Shell)."""
    
    def test_auth_service_with_valid_key(self, monkeypatch):
        """AuthService initializes correctly with valid ENCRYPTION_KEY."""
        from cryptography.fernet import Fernet
        valid_key = Fernet.generate_key().decode()
        
        monkeypatch.setenv("ENCRYPTION_KEY", valid_key)
        
        # Reset singleton
        import api.services.auth_service as auth_service_module
        auth_service_module._auth_service = None
        
        from api.services.auth_service import AuthService
        service = AuthService()
        
        # Should be able to encrypt/decrypt
        encrypted = service.encrypt_github_token("test_token")
        decrypted = service.decrypt_github_token(encrypted)
        assert decrypted == "test_token"
    
    def test_auth_service_fails_in_production_without_key(self, monkeypatch):
        """AuthService raises error in production when ENCRYPTION_KEY is missing."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        
        # Reset singleton
        import api.services.auth_service as auth_service_module
        auth_service_module._auth_service = None
        
        from api.services.auth_service import AuthService, AuthServiceConfigError
        
        with pytest.raises(AuthServiceConfigError) as exc_info:
            AuthService()
        
        assert "ENCRYPTION_KEY must be set in production" in str(exc_info.value)
    
    def test_auth_service_warns_in_development_without_key(self, monkeypatch, caplog):
        """AuthService warns but works in development when ENCRYPTION_KEY is missing."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        
        # Reset singleton
        import api.services.auth_service as auth_service_module
        auth_service_module._auth_service = None
        
        import logging
        caplog.set_level(logging.WARNING)
        
        from api.services.auth_service import AuthService
        service = AuthService()
        
        # Should work (with ephemeral key)
        encrypted = service.encrypt_github_token("test_token")
        assert len(encrypted) > 0
        
        # Should have logged a warning
        assert any("ephemeral key" in record.message for record in caplog.records)
    
    def test_auth_service_invalid_key_format(self, monkeypatch):
        """AuthService raises error when ENCRYPTION_KEY has invalid format."""
        monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
        
        # Reset singleton
        import api.services.auth_service as auth_service_module
        auth_service_module._auth_service = None
        
        from api.services.auth_service import AuthService, AuthServiceConfigError
        
        with pytest.raises(AuthServiceConfigError) as exc_info:
            AuthService()
        
        assert "Invalid ENCRYPTION_KEY format" in str(exc_info.value)
    
    def test_get_auth_service_singleton(self, monkeypatch):
        """get_auth_service returns same instance (singleton pattern)."""
        from cryptography.fernet import Fernet
        valid_key = Fernet.generate_key().decode()
        
        monkeypatch.setenv("ENCRYPTION_KEY", valid_key)
        
        # Reset singleton
        import api.services.auth_service as auth_service_module
        auth_service_module._auth_service = None
        
        from api.services.auth_service import get_auth_service
        
        service1 = get_auth_service()
        service2 = get_auth_service()
        
        assert service1 is service2


class TestLegacyEncryptTokenWrapper:
    """Tests for legacy encrypt_token/decrypt_token wrappers in auth.py."""
    
    def test_legacy_encrypt_token_works(self, monkeypatch):
        """Legacy encrypt_token wrapper delegates to AuthService."""
        from cryptography.fernet import Fernet
        valid_key = Fernet.generate_key().decode()
        
        monkeypatch.setenv("ENCRYPTION_KEY", valid_key)
        
        # Reset singleton
        import api.services.auth_service as auth_service_module
        auth_service_module._auth_service = None
        
        import api.auth
        
        encrypted = api.auth.encrypt_token("legacy_test_token")
        assert len(encrypted) > 0
        
        decrypted = api.auth.decrypt_token(encrypted)
        assert decrypted == "legacy_test_token"
