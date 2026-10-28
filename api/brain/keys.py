"""
Key Manager - Public Key Storage

The keys/ folder stores public keys used for verification.
Currently stores InspecThor's public key for future proof receipt signing.

Keys Structure:
  .inspecthor/keys/
    inspecthor.pub    # InspecThor public key
    user_keys/        # User-specific keys (future)
"""

from pathlib import Path
from typing import Optional


class KeyManager:
    """Manages public keys in .inspecthor/keys/"""

    KEYS_FOLDER = "keys"
    INSPECTHOR_KEY_FILE = "inspecthor.pub"

    def __init__(self, repo_root: str):
        """
        Initialize key manager for a repository

        Args:
            repo_root: Absolute path to repository root
        """
        self.repo_root = Path(repo_root)
        self.keys_path = self.repo_root / ".inspecthor" / self.KEYS_FOLDER

    def initialize(self) -> None:
        """Create keys/ folder and generate initial key"""
        self.keys_path.mkdir(parents=True, exist_ok=True)

        # Create placeholder public key
        # In future, this would be an actual Ed25519 public key
        if not self.has_inspecthor_key():
            self._create_inspecthor_key()

    def has_inspecthor_key(self) -> bool:
        """Check if InspecThor public key exists"""
        key_path = self.keys_path / self.INSPECTHOR_KEY_FILE
        return key_path.exists()

    def get_inspecthor_key(self) -> Optional[str]:
        """
        Get InspecThor public key

        Returns:
            Public key as string or None if not found
        """
        key_path = self.keys_path / self.INSPECTHOR_KEY_FILE

        if not key_path.exists():
            return None

        with open(key_path, 'r') as f:
            return f.read()

    def _create_inspecthor_key(self) -> None:
        """Create placeholder InspecThor public key"""
        key_path = self.keys_path / self.INSPECTHOR_KEY_FILE

        # Placeholder key - in production, this would be generated properly
        placeholder_key = """-----BEGIN PUBLIC KEY-----
InspecThor Public Key (Placeholder)
Version: 1.0.0
Generated: Repository Initialization

This is a placeholder for future proof receipt signing.
In production, this would be a real Ed25519 public key.
-----END PUBLIC KEY-----
"""

        with open(key_path, 'w') as f:
            f.write(placeholder_key)

    def exists(self) -> bool:
        """Check if keys directory exists"""
        return self.keys_path.exists()
