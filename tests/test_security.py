"""
Security-focused tests for he-stain-deconvolver.
"""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.base import (
    PHIGuard,
    AuditTrail,
    AuditLogger,
    SecurityException,
    assert_no_phi,
)


class TestPHIGuard:
    def test_blocks_mrn(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Patient MRN-12345678")

    def test_blocks_ssn(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("SSN: 123-45-6789")

    def test_blocks_phone(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Call 555-123-4567")

    def test_blocks_dob(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("DOB: 01/15/1990")

    def test_blocks_patient_name(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Patient Name: John Smith")

    def test_blocks_common_placeholder_names(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Patient John Doe admitted")

    def test_allows_clean_text(self):
        # Should not raise
        PHIGuard.assert_no_phi("Analytical assay specimen KEY-001 optimal")
        PHIGuard.assert_no_phi("H&E stain deconvolution results for slide A-42")

    def test_allows_empty_string(self):
        PHIGuard.assert_no_phi("")

    def test_allows_none(self):
        PHIGuard.assert_no_phi(None)

    def test_redact_phi(self):
        text = "Patient MRN-12345678 and SSN 123-45-6789"
        redacted = PHIGuard.redact_phi(text)
        assert "MRN" not in redacted
        assert "123-45-6789" not in redacted
        assert "[REDACTED_IDENTIFIER]" in redacted


class TestAuditTrail:
    def test_log_creates_entry(self):
        trail = AuditTrail(secret_key="test-key")
        entry = trail.log("test_actor", "tier1", "TEST_EVENT", {"key": "value"})
        assert entry["audit_id"].startswith("AUDIT-")
        assert entry["actor"] == "test_actor"
        assert entry["event_type"] == "TEST_EVENT"
        assert entry["prev_hash"] == "GENESIS_BLOCK_0000000000000000"

    def test_chain_integrity(self):
        trail = AuditTrail(secret_key="test-key")
        trail.log("actor1", "tier1", "EVENT_1", {"a": 1})
        trail.log("actor2", "tier1", "EVENT_2", {"b": 2})
        trail.log("actor3", "tier1", "EVENT_3", {"c": 3})
        assert trail.verify_integrity() is True

    def test_tamper_detection(self):
        trail = AuditTrail(secret_key="test-key")
        trail.log("actor1", "tier1", "EVENT_1", {"a": 1})
        trail.log("actor2", "tier1", "EVENT_2", {"b": 2})
        # Tamper with the chain
        trail.logs[0]["current_hash"] = "TAMPERED"
        assert trail.verify_integrity() is False

    def test_phi_blocked_in_audit(self):
        trail = AuditTrail(secret_key="test-key")
        with pytest.raises(SecurityException):
            trail.log("actor1", "tier1", "EVENT_1", {"patient": "MRN-12345678"})

    def test_unique_keys_per_instance(self):
        """Each AuditTrail instance without explicit key should have unique key."""
        trail1 = AuditTrail()
        trail2 = AuditTrail()
        assert trail1.secret_key != trail2.secret_key

    def test_env_var_key(self, monkeypatch):
        monkeypatch.setenv("AUDIT_SECRET_KEY", "env-based-key")
        trail = AuditTrail()
        assert trail.secret_key == b"env-based-key"


class TestNoHardcodedSecrets:
    """Verify that no hardcoded secrets exist in source files."""

    def test_no_hardcoded_audit_key_in_base(self):
        base_path = Path(__file__).parent.parent / "agents" / "base.py"
        content = base_path.read_text()
        # The old hardcoded key should not be present
        assert "he-stain-deconvolver-master-audit-key-2026" not in content

    def test_no_hardcoded_key_in_docker_compose(self):
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        content = compose_path.read_text()
        # The old hardcoded key should not be present
        assert "he-stain-deconvolver-prod-audit-key-2026" not in content
