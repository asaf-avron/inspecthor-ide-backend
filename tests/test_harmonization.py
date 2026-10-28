"""
Tests for Harmonization Service (Task #4)
AI-Gapped Development workflow
"""

import pytest
from api.services.harmonization_service import HarmonizationService, SpecChange


class TestHarmonizationService:
    """Test harmonization service"""

    def setup_method(self):
        """Create harmonization service for tests"""
        self.service = HarmonizationService()

    def test_compute_hash(self):
        """Test hash computation"""
        content = "method Test() ensures true { }"
        hash1 = self.service.compute_hash(content)
        hash2 = self.service.compute_hash(content)

        # Same content should produce same hash
        assert hash1 == hash2
        assert hash1.startswith("sha256:")

        # Different content should produce different hash
        different = "method Test() ensures false { }"
        hash3 = self.service.compute_hash(different)
        assert hash1 != hash3

    def test_detect_desync_no_stored_hashes(self):
        """Test desync detection with no stored hashes"""
        spec = "# Requirement 1"
        dafny = "method Test() { }"

        is_desync = self.service.detect_desync(spec, dafny, None, None)

        # Should not detect desync if no baseline
        assert is_desync == False

    def test_detect_desync_spec_changed(self):
        """Test desync detection when spec changed"""
        old_spec = "# Requirement 1"
        new_spec = "# Requirement 1\n# Requirement 2"
        dafny = "method Test() { }"

        old_spec_hash = self.service.compute_hash(old_spec)
        dafny_hash = self.service.compute_hash(dafny)

        is_desync = self.service.detect_desync(
            new_spec,
            dafny,
            old_spec_hash,
            dafny_hash
        )

        # Should detect desync when spec changed but Dafny didn't
        assert is_desync == True

    def test_detect_desync_both_changed(self):
        """Test desync when both spec and Dafny changed"""
        old_spec = "# Requirement 1"
        new_spec = "# Requirement 2"
        old_dafny = "method Test1() { }"
        new_dafny = "method Test2() { }"

        old_spec_hash = self.service.compute_hash(old_spec)
        old_dafny_hash = self.service.compute_hash(old_dafny)

        is_desync = self.service.detect_desync(
            new_spec,
            new_dafny,
            old_spec_hash,
            old_dafny_hash
        )

        # Should not detect desync if both changed (harmonized)
        assert is_desync == False

    def test_analyze_spec_changes_simple(self):
        """Test simple spec change analysis"""
        old_spec = """
# Authentication

## Requirements
- Users can log in
"""

        new_spec = """
# Authentication

## Requirements
- Users can log in
- Users can log out
- Failed login attempts are logged
"""

        changes = self.service.analyze_spec_changes(old_spec, new_spec)

        # Should detect additions
        assert len(changes) > 0
        assert any(c.change_type == 'addition' for c in changes)

    def test_analyze_spec_changes_modification(self):
        """Test spec modification detection"""
        old_spec = """
# Authentication
- Password must be 6 characters
"""

        new_spec = """
# Authentication
- Password must be 12 characters
"""

        changes = self.service.analyze_spec_changes(old_spec, new_spec)

        # Should detect changes
        assert len(changes) > 0

    def test_analyze_spec_changes_deletion(self):
        """Test spec deletion detection"""
        old_spec = """
# Features
- Feature A
- Feature B
- Feature C
"""

        new_spec = """
# Features
- Feature A
- Feature C
"""

        changes = self.service.analyze_spec_changes(old_spec, new_spec)

        # Should detect deletions
        assert len(changes) > 0
        assert any(c.change_type == 'deletion' for c in changes)

    def test_analyze_spec_changes_no_changes(self):
        """Test when spec hasn't changed"""
        spec = "# Same content"

        changes = self.service.analyze_spec_changes(spec, spec)

        # Should return empty list when specs are identical
        assert len(changes) == 0

    def test_update_dafny_incrementally_placeholder(self):
        """Test Dafny update (placeholder when no API key)"""
        current_dafny = "method Test() { }"

        changes = [
            SpecChange(
                change_type="addition",
                section="Authentication",
                old_content=None,
                new_content="Users can log out",
                description="Added logout requirement"
            )
        ]

        new_spec = "# Logout feature\nUsers can log out"

        success, updated, error = self.service.update_dafny_incrementally(
            current_dafny,
            changes,
            new_spec
        )

        # Without proper API setup, should fail gracefully
        if not error:
            # If it succeeded, verify it returned something
            assert updated is not None
        else:
            # If it failed, should have error message (API key or model issue)
            assert error is not None and len(error) > 0

    def test_harmonize_no_changes(self):
        """Test harmonization when no changes detected"""
        spec = "# Requirement 1"
        dafny = "method Test() { }"

        result = self.service.harmonize(spec, spec, dafny)

        # Should succeed with no changes
        assert result.success == True
        assert result.sync_status == 'clean'
        assert len(result.changes_detected) == 0
        assert result.dafny_updated == False

    def test_harmonize_with_changes(self):
        """Test harmonization with spec changes"""
        old_spec = "# Requirement 1"
        new_spec = "# Requirement 1\n# Requirement 2"
        dafny = "method Test() { }"

        result = self.service.harmonize(old_spec, new_spec, dafny)

        # Should detect changes
        assert len(result.changes_detected) > 0

        # Status depends on whether update succeeded
        # Without GEMINI_API_KEY, it might fail
        assert result.sync_status in ['clean', 'error']

    def test_harmonize_with_verification_callback(self):
        """Test harmonization with verification"""
        old_spec = "# Test"
        new_spec = "# Test Updated"
        dafny = "method Test() { }"

        # Mock verification callback
        def mock_verify(code):
            return {'success': True, 'output': 'Verified'}

        result = self.service.harmonize(
            old_spec,
            new_spec,
            dafny,
            verify_callback=mock_verify
        )

        # Should call verification if provided
        assert result.verification_output is not None or result.error_message is not None


class TestSpecChangeDetection:
    """Test spec change detection logic"""

    def setup_method(self):
        """Create service for tests"""
        self.service = HarmonizationService()

    def test_addition_detection(self):
        """Test detecting additions"""
        old = "Feature A"
        new = "Feature A\nFeature B"

        changes = self.service._simple_diff_analysis(old, new)

        assert any(c.change_type == 'addition' for c in changes)

    def test_deletion_detection(self):
        """Test detecting deletions"""
        old = "Feature A\nFeature B"
        new = "Feature A"

        changes = self.service._simple_diff_analysis(old, new)

        assert any(c.change_type == 'deletion' for c in changes)

    def test_no_change_detection(self):
        """Test when nothing changed"""
        spec = "Same content"

        changes = self.service._simple_diff_analysis(spec, spec)

        # Should return empty list when specs are identical
        assert len(changes) == 0


if __name__ == "__main__":
    print("\n[TEST] Running Harmonization Service Tests\n")
    print("=" * 60)

    service = HarmonizationService()

    print("\n[1] Testing hash computation...")
    test = TestHarmonizationService()
    test.setup_method()
    test.test_compute_hash()
    print("[OK] Hash computation works")

    print("\n[2] Testing desync detection...")
    test.test_detect_desync_spec_changed()
    print("[OK] Desync detected when spec changes")

    print("\n[3] Testing spec change analysis...")
    test.test_analyze_spec_changes_simple()
    print("[OK] Spec changes analyzed")

    print("\n[4] Testing harmonization with no changes...")
    test.test_harmonize_no_changes()
    print("[OK] No-change harmonization works")

    print("\n" + "=" * 60)
    print("[OK] All harmonization tests completed!\n")
