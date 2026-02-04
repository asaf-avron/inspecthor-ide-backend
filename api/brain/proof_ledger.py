"""
Proof Ledger - Cryptographic Verification History

The proof ledger stores immutable records of verification states.
Each entry includes:
- Cryptographic hash (SHA256) of the Dafny code
- Verification status and proof obligations
- Timestamp and metadata

This enables tamper detection: if the hash of current code doesn't match
the ledger, the component has been corrupted.

Ledger Structure:
  .inspecthor/proof_ledger/
    {component_uuid}/
      20260204_120000_verified.json
      20260204_153000_verified.json
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class VerificationStatus(str, Enum):
    """Verification status for ledger entries"""
    VERIFIED = "verified"
    FAILED = "failed"
    PENDING = "pending"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ProofObligation:
    """Represents a single proof obligation"""
    name: str
    status: str
    line: Optional[int] = None
    message: Optional[str] = None


@dataclass
class LedgerEntry:
    """Represents a verification entry in the proof ledger"""
    uuid: str
    timestamp: str
    hash: str
    status: str
    proof_obligations: List[Dict]
    dafny_version: Optional[str] = None
    verification_time_ms: Optional[int] = None
    dafny_output: Optional[str] = None
    error_message: Optional[str] = None
    # Cryptographic enhancements
    signature: Optional[str] = None  # Ed25519 signature (base64)
    previous_hash: Optional[str] = None  # Hash of previous entry (chain of custody)
    entry_number: Optional[int] = None  # Sequential entry number


class ProofLedger:
    """Manages the proof ledger in .inspecthor/proof_ledger/"""

    LEDGER_FOLDER = "proof_ledger"

    def __init__(self, repo_root: str, enable_signing: bool = True):
        """
        Initialize proof ledger for a repository

        Args:
            repo_root: Absolute path to repository root
            enable_signing: Whether to enable cryptographic signing
        """
        self.repo_root = Path(repo_root)
        self.ledger_path = self.repo_root / ".inspecthor" / self.LEDGER_FOLDER
        self.keys_path = self.repo_root / ".inspecthor" / "keys"
        self.enable_signing = enable_signing
        self._private_key = None
        self._public_key = None

        # Load keys if signing enabled
        if enable_signing:
            self._load_or_generate_keys()

    def initialize(self) -> None:
        """Create proof_ledger/ folder and keys directory"""
        self.ledger_path.mkdir(parents=True, exist_ok=True)
        self.keys_path.mkdir(parents=True, exist_ok=True)

    def _load_or_generate_keys(self) -> None:
        """Load existing signing keys or generate new ones"""
        private_key_path = self.keys_path / "ledger_private.pem"
        public_key_path = self.keys_path / "ledger_public.pem"

        if private_key_path.exists() and public_key_path.exists():
            # Load existing keys
            with open(private_key_path, 'rb') as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )

            with open(public_key_path, 'rb') as f:
                self._public_key = serialization.load_pem_public_key(f.read())
        else:
            # Generate new keys
            self._private_key = ed25519.Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()

            # Ensure keys directory exists
            self.keys_path.mkdir(parents=True, exist_ok=True)

            # Save private key
            with open(private_key_path, 'wb') as f:
                f.write(self._private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            # Save public key
            with open(public_key_path, 'wb') as f:
                f.write(self._public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))

    def _sign_entry(self, entry_data: Dict) -> str:
        """
        Sign a ledger entry

        Args:
            entry_data: Dictionary of entry data to sign

        Returns:
            Base64-encoded signature
        """
        if not self.enable_signing or not self._private_key:
            return ""

        # Create canonical representation for signing
        # Exclude signature field itself
        sign_data = {k: v for k, v in entry_data.items() if k != 'signature'}
        canonical = json.dumps(sign_data, sort_keys=True)

        # Sign
        signature = self._private_key.sign(canonical.encode('utf-8'))

        return base64.b64encode(signature).decode('utf-8')

    def _verify_signature(self, entry: LedgerEntry) -> bool:
        """
        Verify the signature of a ledger entry

        Args:
            entry: LedgerEntry to verify

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.enable_signing or not entry.signature:
            return True  # No signature to verify

        if not self._public_key:
            return False

        try:
            # Recreate canonical representation
            entry_dict = asdict(entry)
            sign_data = {k: v for k, v in entry_dict.items() if k != 'signature'}
            canonical = json.dumps(sign_data, sort_keys=True)

            # Verify signature
            signature_bytes = base64.b64decode(entry.signature)
            self._public_key.verify(signature_bytes, canonical.encode('utf-8'))

            return True
        except (InvalidSignature, Exception):
            return False

    def record_verification(
        self,
        component_uuid: str,
        dafny_code: str,
        status: VerificationStatus,
        proof_obligations: List[Dict],
        dafny_version: Optional[str] = None,
        verification_time_ms: Optional[int] = None,
        dafny_output: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> LedgerEntry:
        """
        Record a verification in the ledger with cryptographic signing

        Args:
            component_uuid: UUID of the component
            dafny_code: The Dafny code that was verified
            status: Verification status
            proof_obligations: List of proof obligations
            dafny_version: Version of Dafny used
            verification_time_ms: Time taken for verification
            dafny_output: Raw output from Dafny
            error_message: Error message if verification failed

        Returns:
            LedgerEntry with signature and chain-of-custody
        """
        # Compute hash of the code
        code_hash = self._compute_hash(dafny_code)

        # Get previous entry for chain of custody
        previous_entry = self.get_latest_entry(component_uuid)
        previous_hash = None
        entry_number = 1

        if previous_entry:
            # Create hash of previous entry for chain link
            previous_dict = asdict(previous_entry)
            previous_canonical = json.dumps(previous_dict, sort_keys=True)
            previous_hash = self._compute_hash(previous_canonical)
            entry_number = (previous_entry.entry_number or 0) + 1

        # Create entry (without signature first)
        timestamp = datetime.utcnow()
        entry = LedgerEntry(
            uuid=component_uuid,
            timestamp=timestamp.isoformat() + 'Z',
            hash=code_hash,
            status=status.value,
            proof_obligations=proof_obligations,
            dafny_version=dafny_version,
            verification_time_ms=verification_time_ms,
            dafny_output=dafny_output,
            error_message=error_message,
            previous_hash=previous_hash,
            entry_number=entry_number
        )

        # Sign the entry
        if self.enable_signing:
            entry_dict = asdict(entry)
            entry.signature = self._sign_entry(entry_dict)

        # Write to file
        self._write_entry(component_uuid, timestamp, entry)

        return entry

    def verify_integrity(self, component_uuid: str, dafny_code: str) -> bool:
        """
        Check if current code matches the latest ledger entry

        Args:
            component_uuid: UUID of the component
            dafny_code: Current Dafny code

        Returns:
            True if hash matches, False if corrupted or no history
        """
        latest = self.get_latest_entry(component_uuid)

        if not latest:
            # No history yet - cannot verify
            return False

        current_hash = self._compute_hash(dafny_code)
        return current_hash == latest.hash

    def get_latest_entry(self, component_uuid: str) -> Optional[LedgerEntry]:
        """
        Get the most recent verification entry for a component

        Args:
            component_uuid: UUID of the component

        Returns:
            LedgerEntry or None if no history
        """
        component_ledger = self.ledger_path / component_uuid

        if not component_ledger.exists():
            return None

        # Get all JSON files, sorted by filename (timestamp)
        entries = sorted(component_ledger.glob("*.json"), reverse=True)

        if not entries:
            return None

        # Read the latest entry
        with open(entries[0], 'r') as f:
            data = json.load(f)
            return LedgerEntry(**data)

    def get_history(
        self,
        component_uuid: str,
        limit: Optional[int] = None
    ) -> List[LedgerEntry]:
        """
        Get verification history for a component

        Args:
            component_uuid: UUID of the component
            limit: Maximum number of entries to return (most recent first)

        Returns:
            List of LedgerEntry, newest first
        """
        component_ledger = self.ledger_path / component_uuid

        if not component_ledger.exists():
            return []

        # Get all JSON files, sorted by filename (timestamp), newest first
        entries = sorted(component_ledger.glob("*.json"), reverse=True)

        if limit:
            entries = entries[:limit]

        result = []
        for entry_file in entries:
            try:
                with open(entry_file, 'r') as f:
                    data = json.load(f)
                    result.append(LedgerEntry(**data))
            except Exception:
                # Skip corrupted entries
                continue

        return result

    def get_hash_history(self, component_uuid: str) -> List[str]:
        """
        Get list of all hashes for a component

        Args:
            component_uuid: UUID of the component

        Returns:
            List of hashes, newest first
        """
        history = self.get_history(component_uuid)
        return [entry.hash for entry in history]

    def has_been_verified(self, component_uuid: str, dafny_code: str) -> bool:
        """
        Check if this exact code has been verified before

        Args:
            component_uuid: UUID of the component
            dafny_code: Dafny code to check

        Returns:
            True if hash exists in history with verified status
        """
        code_hash = self._compute_hash(dafny_code)
        history = self.get_history(component_uuid)

        for entry in history:
            if entry.hash == code_hash and entry.status == VerificationStatus.VERIFIED.value:
                return True

        return False

    def delete_history(self, component_uuid: str) -> bool:
        """
        Delete all ledger entries for a component

        Args:
            component_uuid: UUID of the component

        Returns:
            True if successful, False if component not found
        """
        component_ledger = self.ledger_path / component_uuid

        if not component_ledger.exists():
            return False

        # Remove all files
        for entry_file in component_ledger.glob("*.json"):
            entry_file.unlink()

        # Remove directory
        component_ledger.rmdir()

        return True

    def verify_chain_integrity(self, component_uuid: str) -> Tuple[bool, Optional[str]]:
        """
        Verify the complete chain of custody for a component

        Checks:
        1. Each entry has a valid signature
        2. Each entry correctly links to previous entry
        3. Entry numbers are sequential
        4. No entries are missing from the chain

        Args:
            component_uuid: UUID of the component

        Returns:
            Tuple of (is_valid, error_message)
        """
        history = self.get_history(component_uuid)

        if not history:
            return True, None  # Empty history is valid

        # Reverse to check from oldest to newest
        history = list(reversed(history))

        for i, entry in enumerate(history):
            # Check signature
            if self.enable_signing and entry.signature:
                if not self._verify_signature(entry):
                    return False, f"Invalid signature at entry #{entry.entry_number}"

            # Check entry number is sequential
            expected_number = i + 1
            if entry.entry_number != expected_number:
                return False, f"Entry number mismatch: expected {expected_number}, got {entry.entry_number}"

            # Check chain linkage (skip first entry)
            if i > 0:
                previous_entry = history[i - 1]

                # Compute expected previous hash
                previous_dict = asdict(previous_entry)
                previous_canonical = json.dumps(previous_dict, sort_keys=True)
                expected_previous_hash = self._compute_hash(previous_canonical)

                if entry.previous_hash != expected_previous_hash:
                    return False, f"Chain broken at entry #{entry.entry_number}: previous hash mismatch"

        return True, None

    def get_chain_summary(self, component_uuid: str) -> Dict:
        """
        Get summary of ledger chain for a component

        Args:
            component_uuid: UUID of the component

        Returns:
            Dictionary with chain statistics
        """
        history = self.get_history(component_uuid)

        if not history:
            return {
                'total_entries': 0,
                'verified_count': 0,
                'failed_count': 0,
                'chain_valid': True,
                'first_verification': None,
                'last_verification': None
            }

        verified_count = sum(1 for e in history if e.status == VerificationStatus.VERIFIED.value)
        failed_count = sum(1 for e in history if e.status == VerificationStatus.FAILED.value)

        # Check chain integrity
        chain_valid, error = self.verify_chain_integrity(component_uuid)

        return {
            'total_entries': len(history),
            'verified_count': verified_count,
            'failed_count': failed_count,
            'chain_valid': chain_valid,
            'chain_error': error,
            'first_verification': history[-1].timestamp if history else None,
            'last_verification': history[0].timestamp if history else None,
            'signing_enabled': self.enable_signing
        }

    def export_chain(self, component_uuid: str) -> List[Dict]:
        """
        Export the complete chain of custody as a list of dictionaries

        Args:
            component_uuid: UUID of the component

        Returns:
            List of entry dictionaries, oldest first
        """
        history = self.get_history(component_uuid)
        return [asdict(entry) for entry in reversed(history)]

    def _compute_hash(self, content: str) -> str:
        """
        Compute SHA256 hash of content

        Args:
            content: String content to hash

        Returns:
            Hex-encoded SHA256 hash with 'sha256:' prefix
        """
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return f"sha256:{hash_obj.hexdigest()}"

    def _write_entry(
        self,
        component_uuid: str,
        timestamp: datetime,
        entry: LedgerEntry
    ) -> None:
        """
        Write ledger entry to file

        Args:
            component_uuid: UUID of the component
            timestamp: Timestamp for filename
            entry: LedgerEntry to write
        """
        # Create component ledger directory
        component_ledger = self.ledger_path / component_uuid
        component_ledger.mkdir(parents=True, exist_ok=True)

        # Format: 20260204_120000_123456_verified.json (with microseconds for uniqueness)
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S_%f')}_{entry.status}.json"
        entry_path = component_ledger / filename

        # Write entry
        with open(entry_path, 'w') as f:
            json.dump(asdict(entry), f, indent=2)

    def exists(self) -> bool:
        """Check if ledger directory exists"""
        return self.ledger_path.exists()
