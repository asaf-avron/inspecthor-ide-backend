"""
Tests for Cryptographic Proof Ledger (Task #7)
Enhanced ledger with digital signatures and chain of custody
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from api.brain.proof_ledger import ProofLedger, VerificationStatus, LedgerEntry


class TestCryptographicProofLedger:
    """Test cryptographic features of proof ledger"""

    def setup_method(self):
        """Create temporary test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.ledger = ProofLedger(self.temp_dir, enable_signing=True)
        self.ledger.initialize()

    def teardown_method(self):
        """Clean up temporary directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_key_generation(self):
        """Test that signing keys are generated"""
        keys_path = Path(self.temp_dir) / ".inspecthor" / "keys"

        assert keys_path.exists()
        assert (keys_path / "ledger_private.pem").exists()
        assert (keys_path / "ledger_public.pem").exists()

    def test_key_persistence(self):
        """Test that keys are persisted and reloaded"""
        # First ledger generates keys
        ledger1 = ProofLedger(self.temp_dir, enable_signing=True)
        ledger1.initialize()

        # Record an entry
        entry1 = ledger1.record_verification(
            'test-uuid',
            'method Test1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        signature1 = entry1.signature

        # Second ledger should load same keys
        ledger2 = ProofLedger(self.temp_dir, enable_signing=True)

        # Record another entry - should use same keys
        entry2 = ledger2.record_verification(
            'test-uuid',
            'method Test2() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Both signatures should be verifiable
        assert ledger2._verify_signature(entry1)
        assert ledger2._verify_signature(entry2)

    def test_signature_generation(self):
        """Test that entries are signed"""
        entry = self.ledger.record_verification(
            'test-uuid',
            'method Test() {}',
            VerificationStatus.VERIFIED,
            []
        )

        assert entry.signature is not None
        assert len(entry.signature) > 0

    def test_signature_verification(self):
        """Test signature verification"""
        entry = self.ledger.record_verification(
            'test-uuid',
            'method Test() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Signature should be valid
        assert self.ledger._verify_signature(entry)

    def test_tampered_signature_detection(self):
        """Test that tampered signatures are detected"""
        entry = self.ledger.record_verification(
            'test-uuid',
            'method Test() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Tamper with the entry
        entry.hash = "sha256:tampered"

        # Signature should now be invalid
        assert not self.ledger._verify_signature(entry)

    def test_chain_of_custody_first_entry(self):
        """Test first entry in chain"""
        entry = self.ledger.record_verification(
            'test-uuid',
            'method Test1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # First entry should have no previous hash
        assert entry.previous_hash is None
        assert entry.entry_number == 1

    def test_chain_of_custody_linking(self):
        """Test that entries are linked via previous_hash"""
        entry1 = self.ledger.record_verification(
            'test-uuid',
            'method Test1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        entry2 = self.ledger.record_verification(
            'test-uuid',
            'method Test2() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Second entry should link to first
        assert entry2.previous_hash is not None
        assert entry2.entry_number == 2

        # Verify the link
        from dataclasses import asdict
        import json

        entry1_dict = asdict(entry1)
        entry1_canonical = json.dumps(entry1_dict, sort_keys=True)
        expected_previous_hash = self.ledger._compute_hash(entry1_canonical)

        assert entry2.previous_hash == expected_previous_hash

    def test_chain_integrity_verification(self):
        """Test verifying complete chain integrity"""
        # Create a chain of 5 entries
        for i in range(5):
            self.ledger.record_verification(
                'test-uuid',
                f'method Test{i}() {{}}',
                VerificationStatus.VERIFIED,
                []
            )

        # Chain should be valid
        is_valid, error = self.ledger.verify_chain_integrity('test-uuid')
        assert is_valid
        assert error is None

    def test_chain_integrity_broken_link(self):
        """Test detection of broken chain link"""
        # Create chain
        entry1 = self.ledger.record_verification(
            'test-uuid',
            'method Test1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        entry2 = self.ledger.record_verification(
            'test-uuid',
            'method Test2() {}',
            VerificationStatus.VERIFIED,
            []
        )

        entry3 = self.ledger.record_verification(
            'test-uuid',
            'method Test3() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Tamper with middle entry's hash (breaks chain)
        history = self.ledger.get_history('test-uuid')
        middle_entry_file = None

        component_ledger = Path(self.temp_dir) / ".inspecthor" / "proof_ledger" / "test-uuid"
        for entry_file in component_ledger.glob("*.json"):
            import json
            with open(entry_file, 'r') as f:
                data = json.load(f)
                if data['entry_number'] == 2:
                    middle_entry_file = entry_file
                    break

        if middle_entry_file:
            with open(middle_entry_file, 'r') as f:
                data = json.load(f)

            # Tamper with hash
            data['hash'] = 'sha256:tampered'

            with open(middle_entry_file, 'w') as f:
                json.dump(data, f)

            # Chain should now be invalid
            is_valid, error = self.ledger.verify_chain_integrity('test-uuid')
            assert not is_valid
            assert error is not None

    def test_entry_numbers_sequential(self):
        """Test that entry numbers are sequential"""
        entries = []
        for i in range(10):
            entry = self.ledger.record_verification(
                'test-uuid',
                f'method Test{i}() {{}}',
                VerificationStatus.VERIFIED,
                []
            )
            entries.append(entry)

        for i, entry in enumerate(entries, start=1):
            assert entry.entry_number == i

    def test_chain_summary(self):
        """Test getting chain summary"""
        # Create some entries
        self.ledger.record_verification(
            'test-uuid',
            'method Test1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        self.ledger.record_verification(
            'test-uuid',
            'method Test2() {}',
            VerificationStatus.FAILED,
            []
        )

        self.ledger.record_verification(
            'test-uuid',
            'method Test3() {}',
            VerificationStatus.VERIFIED,
            []
        )

        summary = self.ledger.get_chain_summary('test-uuid')

        assert summary['total_entries'] == 3
        assert summary['verified_count'] == 2
        assert summary['failed_count'] == 1
        assert summary['chain_valid'] == True
        assert summary['signing_enabled'] == True
        assert summary['first_verification'] is not None
        assert summary['last_verification'] is not None

    def test_chain_export(self):
        """Test exporting complete chain"""
        # Create chain
        for i in range(3):
            self.ledger.record_verification(
                'test-uuid',
                f'method Test{i}() {{}}',
                VerificationStatus.VERIFIED,
                []
            )

        chain = self.ledger.export_chain('test-uuid')

        # Should be oldest first
        assert len(chain) == 3
        assert chain[0]['entry_number'] == 1
        assert chain[1]['entry_number'] == 2
        assert chain[2]['entry_number'] == 3

        # Each entry should have a signature
        for entry_dict in chain:
            assert 'signature' in entry_dict
            assert entry_dict['signature'] is not None

    def test_empty_chain_validity(self):
        """Test that empty chain is considered valid"""
        is_valid, error = self.ledger.verify_chain_integrity('nonexistent-uuid')
        assert is_valid
        assert error is None

    def test_signing_disabled(self):
        """Test ledger with signing disabled"""
        ledger_no_sign = ProofLedger(self.temp_dir, enable_signing=False)
        ledger_no_sign.initialize()

        entry = ledger_no_sign.record_verification(
            'test-uuid',
            'method Test() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Should have no signature
        assert entry.signature is None or entry.signature == ""

    def test_multiple_components_independent_chains(self):
        """Test that different components have independent chains"""
        # Create chain for component A
        self.ledger.record_verification(
            'component-a',
            'method A1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        self.ledger.record_verification(
            'component-a',
            'method A2() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Create chain for component B
        self.ledger.record_verification(
            'component-b',
            'method B1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Each should have independent chains
        summary_a = self.ledger.get_chain_summary('component-a')
        summary_b = self.ledger.get_chain_summary('component-b')

        assert summary_a['total_entries'] == 2
        assert summary_b['total_entries'] == 1

        # Both chains should be valid
        is_valid_a, _ = self.ledger.verify_chain_integrity('component-a')
        is_valid_b, _ = self.ledger.verify_chain_integrity('component-b')

        assert is_valid_a
        assert is_valid_b

    def test_proof_obligations_preserved(self):
        """Test that proof obligations are preserved in chain"""
        proof_obligations = [
            {'name': 'ValidateToken', 'status': 'verified'},
            {'name': 'SessionInvariant', 'status': 'verified'}
        ]

        entry = self.ledger.record_verification(
            'test-uuid',
            'method Test() {}',
            VerificationStatus.VERIFIED,
            proof_obligations,
            dafny_version='4.5.0',
            verification_time_ms=1250
        )

        # Retrieve and check
        latest = self.ledger.get_latest_entry('test-uuid')

        assert latest.proof_obligations == proof_obligations
        assert latest.dafny_version == '4.5.0'
        assert latest.verification_time_ms == 1250

    def test_chain_integrity_with_different_statuses(self):
        """Test chain integrity with mixed verification statuses"""
        self.ledger.record_verification(
            'test-uuid',
            'method Test1() {}',
            VerificationStatus.VERIFIED,
            []
        )

        self.ledger.record_verification(
            'test-uuid',
            'method Test2() {}',
            VerificationStatus.FAILED,
            [],
            error_message="Postcondition violation"
        )

        self.ledger.record_verification(
            'test-uuid',
            'method Test3() {}',
            VerificationStatus.VERIFIED,
            []
        )

        # Chain should still be valid (status doesn't affect chain integrity)
        is_valid, error = self.ledger.verify_chain_integrity('test-uuid')
        assert is_valid
        assert error is None


if __name__ == "__main__":
    print("\n[TEST] Running Cryptographic Proof Ledger Tests\n")
    print("=" * 60)

    test = TestCryptographicProofLedger()

    print("\n[1] Testing key generation...")
    test.setup_method()
    test.test_key_generation()
    test.teardown_method()
    print("[OK] Keys generated")

    print("\n[2] Testing signature generation...")
    test.setup_method()
    test.test_signature_generation()
    test.teardown_method()
    print("[OK] Signatures created")

    print("\n[3] Testing chain of custody...")
    test.setup_method()
    test.test_chain_of_custody_linking()
    test.teardown_method()
    print("[OK] Chain linkage works")

    print("\n[4] Testing chain integrity verification...")
    test.setup_method()
    test.test_chain_integrity_verification()
    test.teardown_method()
    print("[OK] Chain integrity verified")

    print("\n" + "=" * 60)
    print("[OK] All cryptographic ledger tests completed!\n")
