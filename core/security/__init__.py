"""
Security module for Inspecthor.
Contains pure cryptographic functions following the Functional Core pattern.
"""

from core.security.crypto import (
    EncryptResult,
    DecryptResult,
    encrypt_token,
    decrypt_token,
    validate_key,
)

__all__ = [
    "EncryptResult",
    "DecryptResult",
    "encrypt_token",
    "decrypt_token",
    "validate_key",
]
