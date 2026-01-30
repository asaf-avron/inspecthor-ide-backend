"""
Trust Registry: Ground truth store for Dafny specifications (.dfy traits).

Per the Architectural Directive, the specification is the immutable contract.
The verification pipeline reads the contract from the Trust Registry when
verifying Python implementations (e.g. by spec_id).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


@dataclass
class SpecEntry:
    """A single spec entry in the Trust Registry."""
    spec_id: str
    content: str  # Dafny contract (trait or method signature + requires/ensures)
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class TrustRegistry:
    """
    In-memory store for Dafny specs (ground truth).
    Can be extended to persist to DB or file.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, SpecEntry] = {}

    def register(self, spec_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> SpecEntry:
        """Register a spec as ground truth. Overwrites if spec_id exists."""
        entry = SpecEntry(
            spec_id=spec_id,
            content=content.strip(),
            created_at=datetime.utcnow().isoformat() + "Z",
            metadata=metadata or {},
        )
        self._specs[spec_id] = entry
        logger.info("Trust Registry: registered spec %s", spec_id)
        return entry

    def get(self, spec_id: str) -> Optional[SpecEntry]:
        """Get a spec by id. Returns None if not found."""
        return self._specs.get(spec_id)

    def get_contract(self, spec_id: str) -> Optional[str]:
        """Get contract content by spec_id. Returns None if not found."""
        entry = self.get(spec_id)
        return entry.content if entry else None

    def list_specs(self) -> List[SpecEntry]:
        """List all registered specs."""
        return list(self._specs.values())

    def delete(self, spec_id: str) -> bool:
        """Remove a spec. Returns True if removed."""
        if spec_id in self._specs:
            del self._specs[spec_id]
            return True
        return False


# Singleton for API use
_trust_registry: Optional[TrustRegistry] = None


def get_trust_registry() -> TrustRegistry:
    """Get the global Trust Registry instance."""
    global _trust_registry
    if _trust_registry is None:
        _trust_registry = TrustRegistry()
    return _trust_registry
