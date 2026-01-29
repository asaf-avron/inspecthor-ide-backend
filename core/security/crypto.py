"""
Pure cryptographic functions for token encryption/decryption.

This module is part of the Functional Core - NO I/O, NO SIDE EFFECTS.
All functions are pure: given the same inputs, they produce the same outputs.

See: api/verification/crypto_contract.dfy for formal specification.
"""

from dataclasses import dataclass
from cryptography.fernet import Fernet, InvalidToken


@dataclass(frozen=True)
class EncryptResult:
    """
    Result of an encryption operation.
    Immutable dataclass following Result pattern from Dafny specs.
    """
    success: bool
    ciphertext: str = ""
    error: str = ""


@dataclass(frozen=True)
class DecryptResult:
    """
    Result of a decryption operation.
    Immutable dataclass following Result pattern from Dafny specs.
    """
    success: bool
    plaintext: str = ""
    error: str = ""


def encrypt_token(key_bytes: bytes, plaintext: str) -> EncryptResult:
    """
    Pure encryption: key + plaintext -> ciphertext.
    
    Args:
        key_bytes: Valid Fernet key (32 bytes, base64-encoded = 44 chars)
        plaintext: String to encrypt
    
    Returns:
        EncryptResult with success=True and ciphertext, or success=False and error
    
    Note:
        Fernet encryption is non-deterministic due to random IV.
        Two calls with same inputs may produce different ciphertexts.
    """
    try:
        f = Fernet(key_bytes)
        ciphertext = f.encrypt(plaintext.encode()).decode()
        return EncryptResult(success=True, ciphertext=ciphertext)
    except Exception as e:
        return EncryptResult(success=False, error=str(e))


def decrypt_token(key_bytes: bytes, ciphertext: str) -> DecryptResult:
    """
    Pure decryption: key + ciphertext -> plaintext.
    
    Args:
        key_bytes: Valid Fernet key (must match key used for encryption)
        ciphertext: Encrypted string from encrypt_token
    
    Returns:
        DecryptResult with success=True and plaintext, or success=False and error
    
    Postcondition (Round-trip safety):
        For any valid key k and string s:
        decrypt_token(k, encrypt_token(k, s).ciphertext).plaintext == s
    """
    try:
        f = Fernet(key_bytes)
        plaintext = f.decrypt(ciphertext.encode()).decode()
        return DecryptResult(success=True, plaintext=plaintext)
    except InvalidToken:
        return DecryptResult(success=False, error="Invalid token or key")
    except Exception as e:
        return DecryptResult(success=False, error=str(e))


def validate_key(key_bytes: bytes) -> bool:
    """
    Validate that key_bytes is a valid Fernet key.
    
    A valid Fernet key is:
    - 32 bytes of random data
    - Base64-encoded (resulting in 44 characters)
    
    Args:
        key_bytes: Bytes to validate as a Fernet key
    
    Returns:
        True if valid Fernet key, False otherwise
    """
    try:
        Fernet(key_bytes)
        return True
    except Exception:
        return False
