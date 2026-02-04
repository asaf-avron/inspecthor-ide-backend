"""
Tests for Drift Detection Service (Task #9)
AI-Gapped Development workflow - Drift Detection and Repair
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path

from api.services.drift_detector import DriftDetector, DriftIssue, RepairResult
from api.brain.registry import RegistryManager
from api.brain.proof_ledger import ProofLedger, VerificationStatus


class TestDriftDetector:
    """Test drift detection service"""

    def setup_method(self):
        """Create temporary test environment"""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()

        # Initialize Brain structure
        self.inspecthor_dir = os.path.join(self.temp_dir, '.inspecthor')
        os.makedirs(self.inspecthor_dir, exist_ok=True)

        # Create registry manager
        self.registry_manager = RegistryManager(self.temp_dir)

        # Initialize registry
        self.registry_manager.initialize()

        # Create drift detector
        self.detector = DriftDetector(self.temp_dir)

    def teardown_method(self):
        """Clean up temporary directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_component(self, name: str, uuid: str, path: str, add_to_registry: bool = True) -> str:
        """Helper to create a test component"""
        component_path = os.path.join(self.temp_dir, path)
        os.makedirs(component_path, exist_ok=True)

        # Create .inspecthor_meta
        meta = {
            'component_uuid': uuid,
            'name': name,
            'created_at': '2026-02-04T12:00:00Z',
            'type': 'component'
        }

        meta_path = os.path.join(component_path, '.inspecthor_meta')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)

        # Create spec.md
        spec_path = os.path.join(component_path, 'spec.md')
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(f"# {name}\n\nTest component specification")

        # Create core.dfy
        dafny_path = os.path.join(component_path, 'core.dfy')
        with open(dafny_path, 'w', encoding='utf-8') as f:
            f.write(f"method Test{name}() {{}}")

        # Add to registry
        if add_to_registry:
            self.registry_manager.add_component(uuid, path, name)

        return component_path

    def test_scan_clean_repository(self):
        """Test scanning a repository with no drift"""
        # Create test components
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')
        self._create_test_component('Data', 'data-uuid-2', 'data')

        # Scan for drift
        report = self.detector.scan_for_drift()

        # Should find no issues
        assert report.total_issues == 0
        assert report.health_score == 100.0
        assert len(report.issues) == 0

    def test_detect_missing_component(self):
        """Test detecting a component that's in registry but file missing"""
        # Create component and add to registry
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')

        # Delete the component directory
        component_path = os.path.join(self.temp_dir, 'auth')
        shutil.rmtree(component_path)

        # Scan for drift
        report = self.detector.scan_for_drift()

        # Should detect missing component
        assert report.total_issues == 1
        assert report.health_score < 100.0

        issue = report.issues[0]
        assert issue.issue_type == 'missing'
        assert issue.component_uuid == 'auth-uuid-1'
        assert issue.severity == 'high'
        assert issue.repairable == True

    def test_detect_moved_component(self):
        """Test detecting a component that moved to a different location"""
        # Create component at original location
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')

        # Move component to new location
        old_path = os.path.join(self.temp_dir, 'auth')
        new_path = os.path.join(self.temp_dir, 'components', 'auth')
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)

        # Scan for drift
        report = self.detector.scan_for_drift()

        # Should detect moved component
        assert report.total_issues == 1

        issue = report.issues[0]
        assert issue.issue_type == 'moved'
        assert issue.component_uuid == 'auth-uuid-1'
        assert issue.expected_path == 'auth'
        assert 'components' in issue.actual_path
        assert issue.severity == 'medium'
        assert issue.repairable == True

    def test_detect_orphaned_component(self):
        """Test detecting a component on disk but not in registry"""
        # Create component without adding to registry
        self._create_test_component('Auth', 'auth-uuid-1', 'auth', add_to_registry=False)

        # Scan for drift
        report = self.detector.scan_for_drift()

        # Should detect orphaned component
        assert report.total_issues == 1

        issue = report.issues[0]
        assert issue.issue_type == 'orphaned'
        assert issue.component_uuid == 'auth-uuid-1'
        assert issue.severity == 'low'
        assert issue.repairable == True

    def test_detect_corrupted_component(self):
        """Test detecting a component with hash mismatch"""
        # Create component
        component_path = self._create_test_component('Auth', 'auth-uuid-1', 'auth')

        # Record verification in ledger
        dafny_path = os.path.join(component_path, 'core.dfy')
        with open(dafny_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        proof_ledger = ProofLedger(self.temp_dir)
        proof_ledger.record_verification('auth-uuid-1', original_content, VerificationStatus.VERIFIED, [])

        # Modify Dafny file (corruption)
        with open(dafny_path, 'w', encoding='utf-8') as f:
            f.write("method ModifiedTest() {}")

        # Scan for drift
        report = self.detector.scan_for_drift()

        # Should detect corrupted component
        assert report.total_issues == 1

        issue = report.issues[0]
        assert issue.issue_type == 'corrupted'
        assert issue.component_uuid == 'auth-uuid-1'
        assert issue.severity == 'critical'
        assert issue.repairable == False  # Requires manual review

    def test_scan_for_uuid(self):
        """Test scanning for a component by UUID"""
        # Create component
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')

        # Find by UUID
        found_path = self.detector._scan_for_uuid('auth-uuid-1')

        assert found_path is not None
        assert found_path == 'auth'

    def test_scan_for_uuid_not_found(self):
        """Test scanning for non-existent UUID"""
        found_path = self.detector._scan_for_uuid('non-existent-uuid')

        assert found_path is None

    def test_repair_moved_component(self):
        """Test repairing a moved component"""
        # Create component at original location
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')

        # Move component
        old_path = os.path.join(self.temp_dir, 'auth')
        new_path = os.path.join(self.temp_dir, 'moved', 'auth')
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)

        # Repair
        result = self.detector.repair_moved_component('auth-uuid-1')

        # Should succeed
        assert result.success == True
        assert result.component_uuid == 'auth-uuid-1'
        assert result.old_path == 'auth'
        assert 'moved' in result.new_path
        assert result.action_taken == 'updated_registry'

        # Verify registry updated
        component_entry = self.registry_manager.get_component('auth-uuid-1')
        assert component_entry is not None
        assert 'moved' in component_entry.path

    def test_repair_orphaned_component(self):
        """Test repairing an orphaned component"""
        # Create component without registry entry
        self._create_test_component('Auth', 'auth-uuid-1', 'auth', add_to_registry=False)

        # Repair
        result = self.detector.repair_orphaned_component('auth-uuid-1')

        # Should succeed
        assert result.success == True
        assert result.component_uuid == 'auth-uuid-1'
        assert result.new_path == 'auth'
        assert result.action_taken == 'added_to_registry'

        # Verify component in registry
        component_entry = self.registry_manager.get_component('auth-uuid-1')
        assert component_entry is not None
        assert component_entry.path == 'auth'

    def test_auto_repair_all(self):
        """Test auto-repairing all repairable issues"""
        # Create multiple drift issues
        # 1. Moved component
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')
        old_path = os.path.join(self.temp_dir, 'auth')
        new_path = os.path.join(self.temp_dir, 'moved_auth')
        shutil.move(old_path, new_path)

        # 2. Orphaned component
        self._create_test_component('Data', 'data-uuid-2', 'data', add_to_registry=False)

        # Auto-repair
        results = self.detector.auto_repair_all()

        # Should repair both issues
        assert len(results) == 2

        successful = [r for r in results if r.success]
        assert len(successful) == 2

    def test_health_score_calculation(self):
        """Test health score calculation with various issues"""
        # Create multiple issues of different severities
        # Critical issue (corrupted)
        component_path = self._create_test_component('Auth', 'auth-uuid-1', 'auth')
        dafny_path = os.path.join(component_path, 'core.dfy')

        with open(dafny_path, 'r', encoding='utf-8') as f:
            original_content = f.read()

        proof_ledger = ProofLedger(self.temp_dir)
        proof_ledger.record_verification('auth-uuid-1', original_content, VerificationStatus.VERIFIED, [])

        with open(dafny_path, 'w', encoding='utf-8') as f:
            f.write("method Modified() {}")

        # Missing component (high severity)
        self._create_test_component('Data', 'data-uuid-2', 'data')
        data_path = os.path.join(self.temp_dir, 'data')
        shutil.rmtree(data_path)

        # Orphaned component (low severity)
        self._create_test_component('Logic', 'logic-uuid-3', 'logic', add_to_registry=False)

        # Scan
        report = self.detector.scan_for_drift()

        # Should have multiple issues
        assert report.total_issues == 3

        # Health score should be reduced based on severity
        assert report.health_score < 100.0
        assert report.health_score > 0.0

        # Check issue breakdown
        assert report.issues_by_type.get('critical', 0) >= 1
        assert report.issues_by_type.get('high', 0) >= 1
        assert report.issues_by_type.get('low', 0) >= 1

    def test_missing_registry_handling(self):
        """Test handling when registry doesn't exist"""
        # Delete registry
        registry_path = os.path.join(self.inspecthor_dir, 'registry.yaml')
        if os.path.exists(registry_path):
            os.remove(registry_path)

        # Scan should handle gracefully
        report = self.detector.scan_for_drift()

        # Should report critical issue
        assert report.total_issues == 1
        assert report.health_score == 0.0

        issue = report.issues[0]
        assert issue.severity == 'critical'
        assert 'registry' in issue.description.lower()

    def test_find_meta_files(self):
        """Test finding all .inspecthor_meta files"""
        # Create multiple components
        self._create_test_component('Auth', 'auth-uuid-1', 'auth')
        self._create_test_component('Data', 'data-uuid-2', 'subdir/data')

        # Find all meta files
        meta_files = self.detector._find_meta_files()

        # Should find both
        assert len(meta_files) == 2

        # Verify paths
        meta_names = [os.path.basename(os.path.dirname(f)) for f in meta_files]
        assert 'auth' in meta_names
        assert 'data' in meta_names

    def test_find_dafny_file(self):
        """Test finding Dafny file in component directory"""
        # Create component
        component_path = self._create_test_component('Auth', 'auth-uuid-1', 'auth')

        # Find Dafny file
        dafny_path = self.detector._find_dafny_file('auth')

        assert dafny_path is not None
        assert dafny_path.endswith('core.dfy')
        assert os.path.exists(dafny_path)

    def test_multiple_drift_types(self):
        """Test detecting multiple types of drift simultaneously"""
        # Create clean component
        self._create_test_component('Clean', 'clean-uuid', 'clean')

        # Create moved component
        self._create_test_component('Moved', 'moved-uuid', 'original')
        old_path = os.path.join(self.temp_dir, 'original')
        new_path = os.path.join(self.temp_dir, 'new_location')
        shutil.move(old_path, new_path)

        # Create orphaned component
        self._create_test_component('Orphan', 'orphan-uuid', 'orphan', add_to_registry=False)

        # Create missing component
        self._create_test_component('Missing', 'missing-uuid', 'missing')
        missing_path = os.path.join(self.temp_dir, 'missing')
        shutil.rmtree(missing_path)

        # Scan
        report = self.detector.scan_for_drift()

        # Should detect 3 issues (clean component is fine)
        assert report.total_issues == 3

        # Verify issue types
        issue_types = {issue.issue_type for issue in report.issues}
        assert 'moved' in issue_types
        assert 'orphaned' in issue_types
        assert 'missing' in issue_types


if __name__ == "__main__":
    print("\n[TEST] Running Drift Detection Tests\n")
    print("=" * 60)

    # Create temporary test environment
    temp_dir = tempfile.mkdtemp()

    try:
        print("\n[1] Testing clean repository scan...")
        test = TestDriftDetector()
        test.setup_method()
        test.test_scan_clean_repository()
        test.teardown_method()
        print("[OK] Clean repository scan works")

        print("\n[2] Testing moved component detection...")
        test = TestDriftDetector()
        test.setup_method()
        test.test_detect_moved_component()
        test.teardown_method()
        print("[OK] Moved component detected")

        print("\n[3] Testing component repair...")
        test = TestDriftDetector()
        test.setup_method()
        test.test_repair_moved_component()
        test.teardown_method()
        print("[OK] Component repair works")

        print("\n[4] Testing auto-repair...")
        test = TestDriftDetector()
        test.setup_method()
        test.test_auto_repair_all()
        test.teardown_method()
        print("[OK] Auto-repair works")

        print("\n" + "=" * 60)
        print("[OK] All drift detection tests completed!\n")

    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
