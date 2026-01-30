# CryptoContract Specification

**Dafny Spec:** [`api/verification/crypto_contract.dfy`](../../api/verification/crypto_contract.dfy)  
**Python Implementation:** [`core/security/crypto.py`](../../core/security/crypto.py)

## Purpose

Formally verified cryptographic operations for token encryption/decryption using Fernet symmetric encryption. Protects GitHub OAuth tokens at rest.

## Key Functions

### `Encrypt`
Encrypts plaintext using a Fernet key.

**Preconditions:**
- Valid key (44 characters, base64-encoded 32-byte key)

**Postconditions:**
- On success: non-empty ciphertext
- Encryption is non-deterministic (random IV)

### `Decrypt`
Decrypts ciphertext using a Fernet key.

**Preconditions:**
- Valid key
- Non-empty ciphertext

**Postconditions:**
- On success: original plaintext
- On failure: error (wrong key or corrupted data)

## Security Properties

- **RoundTripSafe**: `Decrypt(key, Encrypt(key, plaintext).ciphertext) == plaintext`
- **WrongKeyFails**: Decryption with wrong key fails
- **NonDeterministic**: Same plaintext produces different ciphertexts (security feature)

## Verification Status

✅ Verified with Dafny compiler in CI (`.github/workflows/verify-dafny.yml`)
