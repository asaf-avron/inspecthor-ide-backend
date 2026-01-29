"""
Authentication Service - Imperative Shell for token management.

This module handles I/O and orchestration for authentication operations.
It delegates pure cryptographic operations to the Functional Core.

Pattern: Imperative Shell / Functional Core
Core: core/security/crypto.py
Spec: api/verification/crypto_contract.dfy
"""

import os
import logging
from typing import Optional
from sqlalchemy.orm import Session

from core.security.crypto import encrypt_token, decrypt_token, validate_key
from api.database import User

logger = logging.getLogger(__name__)


class AuthServiceConfigError(Exception):
    """Raised when auth service is misconfigured."""
    pass


class AuthService:
    """
    Orchestrates authentication operations.
    
    Responsibilities (Shell):
    - Read encryption key from environment
    - Validate configuration
    - Coordinate between crypto core and database
    
    Delegates to Core:
    - encrypt_token() for encryption
    - decrypt_token() for decryption
    - validate_key() for key validation
    """
    
    def __init__(self):
        """
        Initialize AuthService with encryption key from environment.
        
        Raises:
            AuthServiceConfigError: If ENCRYPTION_KEY is missing in production
                                   or has invalid format.
        """
        key_str: Optional[str] = os.getenv("ENCRYPTION_KEY")
        
        # SECURITY: Fail fast if no key in production
        if not key_str:
            env = os.getenv("ENVIRONMENT", "development")
            if env == "production":
                raise AuthServiceConfigError(
                    "ENCRYPTION_KEY must be set in production. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            # Dev fallback with warning
            logger.warning(
                "ENCRYPTION_KEY not set - using ephemeral key. "
                "Encrypted data will be lost on restart!"
            )
            from cryptography.fernet import Fernet
            key_str = Fernet.generate_key().decode()
        
        # At this point key_str is guaranteed to be a string
        assert key_str is not None
        self._key = key_str.encode()
        
        if not validate_key(self._key):
            raise AuthServiceConfigError(
                "Invalid ENCRYPTION_KEY format. "
                "Must be a valid Fernet key (44 base64 characters). "
                "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
    
    def encrypt_github_token(self, raw_token: str) -> str:
        """
        Encrypt a GitHub OAuth token for storage.
        
        Args:
            raw_token: Plain GitHub access token
        
        Returns:
            Encrypted token string (safe for database storage)
        
        Raises:
            ValueError: If encryption fails
        """
        result = encrypt_token(self._key, raw_token)
        if not result.success:
            raise ValueError(f"Encryption failed: {result.error}")
        return result.ciphertext
    
    def decrypt_github_token(self, encrypted_token: str) -> str:
        """
        Decrypt a stored GitHub OAuth token.
        
        Args:
            encrypted_token: Encrypted token from database
        
        Returns:
            Plain GitHub access token
        
        Raises:
            ValueError: If decryption fails (wrong key, corrupted data)
        """
        result = decrypt_token(self._key, encrypted_token)
        if not result.success:
            raise ValueError(f"Decryption failed: {result.error}")
        return result.plaintext
    
    def store_user_token(
        self,
        db: Session,
        user: User,
        github_token: str
    ) -> None:
        """
        Encrypt and store a GitHub token for a user.
        
        This is a convenience method that combines encryption and persistence.
        
        Args:
            db: Database session
            user: User object to update
            github_token: Plain GitHub access token
        
        Side effects:
            - Updates user.access_token_encrypted
            - Commits the transaction
        """
        user.access_token_encrypted = self.encrypt_github_token(github_token)  # type: ignore[assignment]
        db.commit()
    
    def get_user_github_token(self, user: User) -> Optional[str]:
        """
        Retrieve and decrypt a user's GitHub token.
        
        Args:
            user: User object with encrypted token
        
        Returns:
            Plain GitHub access token, or None if not set
        
        Raises:
            ValueError: If decryption fails
        """
        if not user.access_token_encrypted:
            return None
        # Cast Column[str] to str for type checker
        encrypted: str = str(user.access_token_encrypted)
        return self.decrypt_github_token(encrypted)


# Module-level singleton for use in auth.py
# Lazy initialization to avoid startup failures during testing
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    """
    Get the singleton AuthService instance.
    
    Lazy initialization allows tests to mock environment before first access.
    
    Returns:
        AuthService singleton instance
    
    Raises:
        AuthServiceConfigError: If service cannot be initialized
    """
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
