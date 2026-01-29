"""
Unit tests for core/security/crypto.py - Pure cryptographic functions.

These tests verify the Functional Core encryption/decryption logic
in isolation from I/O and environment configuration.

Spec: api/verification/crypto_contract.dfy
"""

import pytest
from cryptography.fernet import Fernet

from core.security.crypto import (
    EncryptResult,
    DecryptResult,
    encrypt_token,
    decrypt_token,
    validate_key,
)


class TestValidateKey:
    """Tests for key validation."""
    
    def test_valid_fernet_key(self):
        """Valid Fernet keys should pass validation."""
        key = Fernet.generate_key()
        assert validate_key(key) is True
    
    def test_invalid_key_too_short(self):
        """Keys that are too short should fail validation."""
        key = b"short"
        assert validate_key(key) is False
    
    def test_invalid_key_not_base64(self):
        """Keys that aren't valid base64 should fail validation."""
        key = b"this-is-not-valid-base64-encoded-key!!"
        assert validate_key(key) is False
    
    def test_invalid_key_wrong_length(self):
        """Keys with wrong length should fail validation."""
        # 43 chars instead of 44
        key = b"abcdefghijklmnopqrstuvwxyz123456789012345"
        assert validate_key(key) is False
    
    def test_empty_key(self):
        """Empty key should fail validation."""
        assert validate_key(b"") is False


class TestEncryptToken:
    """Tests for token encryption."""
    
    @pytest.fixture
    def valid_key(self):
        """Generate a valid Fernet key for tests."""
        return Fernet.generate_key()
    
    def test_encrypt_returns_success_result(self, valid_key):
        """Successful encryption returns EncryptResult with success=True."""
        result = encrypt_token(valid_key, "test_token")
        
        assert isinstance(result, EncryptResult)
        assert result.success is True
        assert len(result.ciphertext) > 0
        assert result.error == ""
    
    def test_encrypt_empty_string(self, valid_key):
        """Empty strings can be encrypted (per Dafny spec)."""
        result = encrypt_token(valid_key, "")
        
        assert result.success is True
        assert len(result.ciphertext) > 0  # Ciphertext includes IV and tag
    
    def test_encrypt_unicode_string(self, valid_key):
        """Unicode strings should be encrypted correctly."""
        result = encrypt_token(valid_key, "日本語テスト 🔐")
        
        assert result.success is True
        assert len(result.ciphertext) > 0
    
    def test_encrypt_long_token(self, valid_key):
        """Long tokens should be encrypted correctly."""
        long_token = "a" * 10000
        result = encrypt_token(valid_key, long_token)
        
        assert result.success is True
        assert len(result.ciphertext) > 0
    
    def test_encrypt_with_invalid_key(self):
        """Encryption with invalid key should return failure."""
        invalid_key = b"invalid"
        result = encrypt_token(invalid_key, "test_token")
        
        assert result.success is False
        assert len(result.error) > 0
        assert result.ciphertext == ""
    
    def test_encrypt_non_deterministic(self, valid_key):
        """
        Fernet encryption is non-deterministic (random IV).
        Two encryptions of same plaintext should produce different ciphertexts.
        (Per Dafny spec: Theorem_NonDeterministic)
        """
        plaintext = "same_token"
        
        result1 = encrypt_token(valid_key, plaintext)
        result2 = encrypt_token(valid_key, plaintext)
        
        assert result1.success and result2.success
        # Ciphertexts should differ due to random IV
        assert result1.ciphertext != result2.ciphertext


class TestDecryptToken:
    """Tests for token decryption."""
    
    @pytest.fixture
    def valid_key(self):
        """Generate a valid Fernet key for tests."""
        return Fernet.generate_key()
    
    def test_decrypt_returns_success_result(self, valid_key):
        """Successful decryption returns DecryptResult with success=True."""
        # First encrypt
        encrypt_result = encrypt_token(valid_key, "test_token")
        assert encrypt_result.success
        
        # Then decrypt
        result = decrypt_token(valid_key, encrypt_result.ciphertext)
        
        assert isinstance(result, DecryptResult)
        assert result.success is True
        assert result.plaintext == "test_token"
        assert result.error == ""
    
    def test_decrypt_with_wrong_key_fails(self, valid_key):
        """
        Decryption with wrong key should fail gracefully.
        (Per Dafny spec: WrongKeyFails predicate)
        """
        wrong_key = Fernet.generate_key()
        
        # Encrypt with valid_key
        encrypt_result = encrypt_token(valid_key, "secret_token")
        assert encrypt_result.success
        
        # Decrypt with wrong_key should fail
        result = decrypt_token(wrong_key, encrypt_result.ciphertext)
        
        assert result.success is False
        assert "Invalid token or key" in result.error
        assert result.plaintext == ""
    
    def test_decrypt_corrupted_ciphertext(self, valid_key):
        """Decryption of corrupted ciphertext should fail gracefully."""
        result = decrypt_token(valid_key, "not-valid-ciphertext")
        
        assert result.success is False
        assert len(result.error) > 0
    
    def test_decrypt_empty_ciphertext(self, valid_key):
        """Decryption of empty ciphertext should fail gracefully."""
        result = decrypt_token(valid_key, "")
        
        assert result.success is False
        assert len(result.error) > 0
    
    def test_decrypt_with_invalid_key(self):
        """Decryption with invalid key should fail gracefully."""
        invalid_key = b"invalid"
        result = decrypt_token(invalid_key, "some_ciphertext")
        
        assert result.success is False
        assert len(result.error) > 0


class TestRoundTrip:
    """
    Round-trip tests: Decrypt(Encrypt(x)) == x
    (Per Dafny spec: RoundTripSafe predicate)
    """
    
    @pytest.fixture
    def valid_key(self):
        """Generate a valid Fernet key for tests."""
        return Fernet.generate_key()
    
    def test_round_trip_simple_string(self, valid_key):
        """Simple string round-trips correctly."""
        original = "github_access_token_12345"
        
        encrypted = encrypt_token(valid_key, original)
        assert encrypted.success
        
        decrypted = decrypt_token(valid_key, encrypted.ciphertext)
        assert decrypted.success
        assert decrypted.plaintext == original
    
    def test_round_trip_empty_string(self, valid_key):
        """Empty string round-trips correctly."""
        original = ""
        
        encrypted = encrypt_token(valid_key, original)
        assert encrypted.success
        
        decrypted = decrypt_token(valid_key, encrypted.ciphertext)
        assert decrypted.success
        assert decrypted.plaintext == original
    
    def test_round_trip_unicode(self, valid_key):
        """Unicode string round-trips correctly."""
        original = "トークン 🔑 token"
        
        encrypted = encrypt_token(valid_key, original)
        assert encrypted.success
        
        decrypted = decrypt_token(valid_key, encrypted.ciphertext)
        assert decrypted.success
        assert decrypted.plaintext == original
    
    def test_round_trip_special_characters(self, valid_key):
        """Strings with special characters round-trip correctly."""
        original = "token\n\t\r\0with\x00special\xffchars"
        
        encrypted = encrypt_token(valid_key, original)
        assert encrypted.success
        
        decrypted = decrypt_token(valid_key, encrypted.ciphertext)
        assert decrypted.success
        assert decrypted.plaintext == original
    
    def test_round_trip_long_token(self, valid_key):
        """Long token round-trips correctly."""
        original = "x" * 100000  # 100KB token
        
        encrypted = encrypt_token(valid_key, original)
        assert encrypted.success
        
        decrypted = decrypt_token(valid_key, encrypted.ciphertext)
        assert decrypted.success
        assert decrypted.plaintext == original


class TestDataclassImmutability:
    """Tests to verify result dataclasses are immutable."""
    
    def test_encrypt_result_is_frozen(self):
        """EncryptResult should be immutable."""
        result = EncryptResult(success=True, ciphertext="test")
        
        with pytest.raises(Exception):  # FrozenInstanceError
            result.success = False  # type: ignore
    
    def test_decrypt_result_is_frozen(self):
        """DecryptResult should be immutable."""
        result = DecryptResult(success=True, plaintext="test")
        
        with pytest.raises(Exception):  # FrozenInstanceError
            result.success = False  # type: ignore
