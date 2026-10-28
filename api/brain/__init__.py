"""
Brain Module - The Central Registry and Proof Ledger

The Brain (`.inspecthor/` folder) is the only fixed point in the repository.
It manages:
- registry.yaml: Maps component UUIDs to their paths
- proof_ledger/: Stores cryptographic hashes of verification states
- keys/: Public keys for verification

This module provides the "Embassy" - tracking all InspecThor-managed components
regardless of where they're located in the repository.
"""

from .registry import RegistryManager
from .proof_ledger import ProofLedger
from .keys import KeyManager

__all__ = ['RegistryManager', 'ProofLedger', 'KeyManager']
