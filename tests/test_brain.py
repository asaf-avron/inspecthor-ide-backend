"""
Tests for Brain Architecture (Registry & Proof Ledger)
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from api.brain.registry import RegistryManager, create_component_meta_file, read_component_meta_file
from api.brain.proof_ledger import ProofLedger, VerificationStatus
from api.brain.keys import KeyManager


class TestRegistryManager:
    """Test registry management"""

    def setup_method(self):
        """Create temporary repo for tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.registry = RegistryManager(self.temp_dir)

    def teardown_method(self):
        """Clean up temp directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialize_creates_structure(self):
        """Test that initialize creates .inspecthor/ structure"""
        self.registry.initialize()

        brain_path = Path(self.temp_dir) / ".inspecthor"
        assert brain_path.exists()
        assert (brain_path / "registry.yaml").exists()
        assert (brain_path / "proof_ledger").exists()
        assert (brain_path / "keys").exists()

    def test_add_component(self):
        """Test adding a component to registry"""
        self.registry.initialize()

        entry = self.registry.add_component(
            component_uuid="test-uuid-123",
            path="src/features/auth",
            name="Authentication"
        )

        assert entry.uuid == "test-uuid-123"
        assert entry.path == "src/features/auth"
        assert entry.name == "Authentication"

    def test_get_component(self):
        """Test retrieving a component"""
        self.registry.initialize()

        # Add component
        self.registry.add_component(
            component_uuid="test-uuid-123",
            path="src/features/auth",
            name="Authentication"
        )

        # Retrieve it
        entry = self.registry.get_component("test-uuid-123")

        assert entry is not None
        assert entry.uuid == "test-uuid-123"
        assert entry.path == "src/features/auth"

    def test_update_component_path(self):
        """Test updating component path (drift repair)"""
        self.registry.initialize()

        # Add component
        self.registry.add_component(
            component_uuid="test-uuid-123",
            path="src/features/auth",
            name="Authentication"
        )

        # Update path
        success = self.registry.update_component_path(
            "test-uuid-123",
            "src/legacy/auth"
        )

        assert success
        entry = self.registry.get_component("test-uuid-123")
        assert entry.path == "src/legacy/auth"

    def test_scan_for_uuid(self):
        """Test scanning repository for UUID (drift detection)"""
        self.registry.initialize()

        # Create component directory with meta file
        component_dir = Path(self.temp_dir) / "src" / "features" / "auth"
        component_dir.mkdir(parents=True)
        create_component_meta_file(component_dir, "test-uuid-123")

        # Scan for UUID
        found_path = self.registry.scan_for_uuid("test-uuid-123")

        assert found_path == "src/features/auth"

    def test_find_component_by_path(self):
        """Test finding component by path"""
        self.registry.initialize()

        # Add component
        self.registry.add_component(
            component_uuid="test-uuid-123",
            path="src/features/auth",
            name="Authentication"
        )

        # Find by path
        entry = self.registry.find_component_by_path("src/features/auth")

        assert entry is not None
        assert entry.uuid == "test-uuid-123"


class TestProofLedger:
    """Test proof ledger"""

    def setup_method(self):
        """Create temporary repo for tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.ledger = ProofLedger(self.temp_dir)

    def teardown_method(self):
        """Clean up temp directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialize_creates_ledger(self):
        """Test that initialize creates ledger directory"""
        self.ledger.initialize()

        ledger_path = Path(self.temp_dir) / ".inspecthor" / "proof_ledger"
        assert ledger_path.exists()

    def test_record_verification(self):
        """Test recording a verification"""
        self.ledger.initialize()

        dafny_code = "method Test() ensures true { }"

        entry = self.ledger.record_verification(
            component_uuid="test-uuid-123",
            dafny_code=dafny_code,
            status=VerificationStatus.VERIFIED,
            proof_obligations=[
                {"name": "Test", "status": "verified"}
            ],
            dafny_version="4.5.0",
            verification_time_ms=1250
        )

        assert entry.uuid == "test-uuid-123"
        assert entry.status == "verified"
        assert "sha256:" in entry.hash

    def test_get_latest_entry(self):
        """Test getting latest ledger entry"""
        self.ledger.initialize()

        dafny_code = "method Test() ensures true { }"

        # Record verification
        self.ledger.record_verification(
            component_uuid="test-uuid-123",
            dafny_code=dafny_code,
            status=VerificationStatus.VERIFIED,
            proof_obligations=[]
        )

        # Get latest
        latest = self.ledger.get_latest_entry("test-uuid-123")

        assert latest is not None
        assert latest.uuid == "test-uuid-123"
        assert latest.status == "verified"

    def test_verify_integrity(self):
        """Test integrity verification"""
        self.ledger.initialize()

        dafny_code = "method Test() ensures true { }"

        # Record verification
        self.ledger.record_verification(
            component_uuid="test-uuid-123",
            dafny_code=dafny_code,
            status=VerificationStatus.VERIFIED,
            proof_obligations=[]
        )

        # Verify same code
        is_intact = self.ledger.verify_integrity("test-uuid-123", dafny_code)
        assert is_intact

        # Verify different code (tampered)
        modified_code = "method Test() ensures false { }"
        is_intact = self.ledger.verify_integrity("test-uuid-123", modified_code)
        assert not is_intact

    def test_get_history(self):
        """Test getting verification history"""
        self.ledger.initialize()

        # Record multiple verifications
        for i in range(3):
            self.ledger.record_verification(
                component_uuid="test-uuid-123",
                dafny_code=f"method Test{i}() {{ }}",
                status=VerificationStatus.VERIFIED,
                proof_obligations=[]
            )

        # Get history
        history = self.ledger.get_history("test-uuid-123")

        assert len(history) == 3
        # Should be in reverse chronological order (newest first)

    def test_has_been_verified(self):
        """Test checking if code has been verified before"""
        self.ledger.initialize()

        dafny_code = "method Test() ensures true { }"

        # Record verification
        self.ledger.record_verification(
            component_uuid="test-uuid-123",
            dafny_code=dafny_code,
            status=VerificationStatus.VERIFIED,
            proof_obligations=[]
        )

        # Check if verified
        assert self.ledger.has_been_verified("test-uuid-123", dafny_code)

        # Check different code
        assert not self.ledger.has_been_verified("test-uuid-123", "method Other() { }")


class TestKeyManager:
    """Test key manager"""

    def setup_method(self):
        """Create temporary repo for tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.keys = KeyManager(self.temp_dir)

    def teardown_method(self):
        """Clean up temp directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialize_creates_keys(self):
        """Test that initialize creates keys directory"""
        self.keys.initialize()

        keys_path = Path(self.temp_dir) / ".inspecthor" / "keys"
        assert keys_path.exists()
        assert (keys_path / "inspecthor.pub").exists()

    def test_get_inspecthor_key(self):
        """Test getting InspecThor public key"""
        self.keys.initialize()

        key = self.keys.get_inspecthor_key()

        assert key is not None
        assert "BEGIN PUBLIC KEY" in key


class TestComponentMetaFile:
    """Test component meta file operations"""

    def setup_method(self):
        """Create temporary directory"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up temp directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_meta_file(self):
        """Test creating .inspecthor_meta file"""
        component_path = Path(self.temp_dir)
        create_component_meta_file(component_path, "test-uuid-123")

        meta_path = component_path / ".inspecthor_meta"
        assert meta_path.exists()

    def test_read_meta_file(self):
        """Test reading .inspecthor_meta file"""
        component_path = Path(self.temp_dir)
        create_component_meta_file(component_path, "test-uuid-123")

        meta_data = read_component_meta_file(component_path)

        assert meta_data is not None
        assert meta_data['uuid'] == "test-uuid-123"
        assert 'created' in meta_data
        assert 'inspecthor_version' in meta_data
