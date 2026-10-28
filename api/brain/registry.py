"""
Registry Manager - UUID-based Component Tracking

The registry.yaml file maps component UUIDs to their current paths in the repository.
This enables "Fractal Isolation" - components can be moved anywhere, and InspecThor
will track them by UUID rather than path.

Registry Format:
  version: "1.0"
  components:
    auth-component-abc123:
      path: src/features/authentication
      name: Authentication
      created_at: 2026-02-04T12:00:00Z
      last_verified_at: 2026-02-04T15:30:00Z
"""

import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class ComponentRegistryEntry:
    """Represents a component in the registry"""
    uuid: str
    path: str
    name: str
    created_at: str
    last_verified_at: Optional[str] = None
    last_modified_at: Optional[str] = None


class RegistryManager:
    """Manages the registry.yaml file in .inspecthor/"""

    BRAIN_FOLDER = ".inspecthor"
    REGISTRY_FILE = "registry.yaml"

    def __init__(self, repo_root: str):
        """
        Initialize registry manager for a repository

        Args:
            repo_root: Absolute path to repository root
        """
        self.repo_root = Path(repo_root)
        self.brain_path = self.repo_root / self.BRAIN_FOLDER
        self.registry_path = self.brain_path / self.REGISTRY_FILE

    def initialize(self) -> None:
        """Create .inspecthor/ folder and initial registry.yaml"""
        # Create brain folder
        self.brain_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.brain_path / "proof_ledger").mkdir(exist_ok=True)
        (self.brain_path / "keys").mkdir(exist_ok=True)

        # Create initial registry if it doesn't exist
        if not self.registry_path.exists():
            initial_registry = {
                'version': '1.0',
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'components': {}
            }
            self._write_registry(initial_registry)

    def add_component(
        self,
        component_uuid: str,
        path: str,
        name: str
    ) -> ComponentRegistryEntry:
        """
        Add a component to the registry

        Args:
            component_uuid: UUID of the component
            path: Relative path from repo root (e.g., "src/features/auth")
            name: Human-readable name

        Returns:
            ComponentRegistryEntry
        """
        registry = self._read_registry()

        entry = ComponentRegistryEntry(
            uuid=component_uuid,
            path=path,
            name=name,
            created_at=datetime.utcnow().isoformat() + 'Z'
        )

        registry['components'][component_uuid] = asdict(entry)
        self._write_registry(registry)

        return entry

    def update_component_path(self, component_uuid: str, new_path: str) -> bool:
        """
        Update a component's path (used for drift detection)

        Args:
            component_uuid: UUID of the component
            new_path: New relative path

        Returns:
            True if successful, False if component not found
        """
        registry = self._read_registry()

        if component_uuid not in registry['components']:
            return False

        registry['components'][component_uuid]['path'] = new_path
        registry['components'][component_uuid]['last_modified_at'] = (
            datetime.utcnow().isoformat() + 'Z'
        )

        self._write_registry(registry)
        return True

    def update_verification_time(self, component_uuid: str) -> bool:
        """
        Update the last verification timestamp

        Args:
            component_uuid: UUID of the component

        Returns:
            True if successful, False if component not found
        """
        registry = self._read_registry()

        if component_uuid not in registry['components']:
            return False

        registry['components'][component_uuid]['last_verified_at'] = (
            datetime.utcnow().isoformat() + 'Z'
        )

        self._write_registry(registry)
        return True

    def get_component(self, component_uuid: str) -> Optional[ComponentRegistryEntry]:
        """
        Get a component entry by UUID

        Args:
            component_uuid: UUID of the component

        Returns:
            ComponentRegistryEntry or None if not found
        """
        registry = self._read_registry()

        if component_uuid not in registry['components']:
            return None

        data = registry['components'][component_uuid]
        return ComponentRegistryEntry(**data)

    def get_all_components(self) -> Dict[str, ComponentRegistryEntry]:
        """
        Get all components in the registry

        Returns:
            Dictionary mapping UUID to ComponentRegistryEntry
        """
        registry = self._read_registry()

        return {
            uuid: ComponentRegistryEntry(**data)
            for uuid, data in registry['components'].items()
        }

    def remove_component(self, component_uuid: str) -> bool:
        """
        Remove a component from the registry

        Args:
            component_uuid: UUID of the component

        Returns:
            True if successful, False if component not found
        """
        registry = self._read_registry()

        if component_uuid not in registry['components']:
            return False

        del registry['components'][component_uuid]
        self._write_registry(registry)
        return True

    def find_component_by_path(self, path: str) -> Optional[ComponentRegistryEntry]:
        """
        Find a component by its current path

        Args:
            path: Relative path to search for

        Returns:
            ComponentRegistryEntry or None if not found
        """
        registry = self._read_registry()

        for uuid, data in registry['components'].items():
            if data['path'] == path:
                return ComponentRegistryEntry(**data)

        return None

    def scan_for_uuid(self, component_uuid: str) -> Optional[str]:
        """
        Scan the repository for .inspecthor_meta file containing UUID
        Used for drift detection when registry path is incorrect

        Args:
            component_uuid: UUID to search for

        Returns:
            Relative path if found, None otherwise
        """
        for root, dirs, files in os.walk(self.repo_root):
            # Skip .inspecthor folder itself
            if self.BRAIN_FOLDER in root:
                continue

            if '.inspecthor_meta' in files:
                meta_path = Path(root) / '.inspecthor_meta'
                try:
                    with open(meta_path, 'r') as f:
                        meta_data = yaml.safe_load(f)
                        if meta_data and meta_data.get('uuid') == component_uuid:
                            # Return relative path from repo root (use forward slashes for consistency)
                            return Path(root).relative_to(self.repo_root).as_posix()
                except Exception:
                    continue

        return None

    def exists(self) -> bool:
        """Check if registry exists"""
        return self.registry_path.exists()

    def _read_registry(self) -> dict:
        """Read registry.yaml file"""
        if not self.registry_path.exists():
            return {
                'version': '1.0',
                'created_at': datetime.utcnow().isoformat() + 'Z',
                'components': {}
            }

        with open(self.registry_path, 'r') as f:
            registry: Dict[Any, Any] = yaml.safe_load(f)
            return registry

    def _write_registry(self, registry: dict) -> None:
        """Write registry.yaml file"""
        with open(self.registry_path, 'w') as f:
            yaml.dump(registry, f, default_flow_style=False, sort_keys=False)


def create_component_meta_file(component_path: Path, component_uuid: str) -> None:
    """
    Create .inspecthor_meta file in component directory

    Args:
        component_path: Absolute path to component directory
        component_uuid: UUID to store in meta file
    """
    meta_path = component_path / '.inspecthor_meta'
    meta_data = {
        'uuid': component_uuid,
        'created': datetime.utcnow().isoformat() + 'Z',
        'inspecthor_version': '1.0.0'
    }

    with open(meta_path, 'w') as f:
        yaml.dump(meta_data, f, default_flow_style=False)


def read_component_meta_file(component_path: Path) -> Optional[Dict]:
    """
    Read .inspecthor_meta file from component directory

    Args:
        component_path: Absolute path to component directory

    Returns:
        Dictionary with meta data or None if not found
    """
    meta_path = component_path / '.inspecthor_meta'

    if not meta_path.exists():
        return None

    try:
        with open(meta_path, 'r') as f:
            meta: Optional[Dict[Any, Any]] = yaml.safe_load(f)
            return meta
    except Exception:
        return None
