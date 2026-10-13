"""Regressions for audit integrity, numeric inputs, and CSV parsing."""
import argparse
import numpy as np
import pytest

from agents.base import AuditTrail
from cli import parse_csv_bool
from he_stain_deconvolver.cli import parse_vector, build_parser, resolve_stain_setup
from he_stain_deconvolver.stains import normalize_vector


def test_tamper_last_hmac_block_detected():
    trail = AuditTrail(secret_key="unit-test-key")
    trail.log("lab", "tier1", "TEST", {"count": 1})
    trail.logs[-1]["current_hash"] = "0" * 64
    assert trail.verify_integrity() is False


def test_tamper_signed_metadata_detected():
    trail = AuditTrail(secret_key="unit-test-key")
    trail.log("lab", "tier1", "TEST", {"count": 1})
    trail.logs[0]["actor"] = "altered"
    assert trail.verify_integrity() is False


def test_exported_audit_trail_is_copy():
    trail = AuditTrail(secret_key="unit-test-key")
    trail.log("lab", "tier1", "TEST", {"count": 1})
    snapshot = trail.get_trail()
    snapshot[0]["actor"] = "tampered copy"
    assert trail.verify_integrity() is True


@pytest.mark.parametrize("value, expected", [("false", False), ("FALSE", False), ("0", False),
                                             ("", False), ("yes", True), ("1", True), ("True", True)])
def test_parse_csv_boolean(value, expected):
    assert parse_csv_bool(value) is expected


def test_invalid_csv_boolean_rejected():
    with pytest.raises(ValueError):
        parse_csv_bool("maybe")


@pytest.mark.parametrize("value", ["nan,0.2,0.3", "inf,0.2,0.3", "-inf,0.2,0.3"])
def test_nonfinite_cli_vector_rejected(value):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_vector(value)


@pytest.mark.parametrize("vector", [[np.nan, 1, 2], [1, 2], [1, 2, np.inf], [0, 0, 0]])
def test_invalid_stain_vectors_rejected(vector):
    with pytest.raises(ValueError):
        normalize_vector(vector)


def test_duplicate_custom_stain_names_rejected():
    args = build_parser().parse_args(["slide.png", "--custom-vectors", "0.6,0.7,0.3",
                                      "0.1,0.9,0.1", "--stain-names", "one", "one"])
    with pytest.raises(ValueError):
        resolve_stain_setup(args)


def test_unsafe_stain_name_rejected():
    args = build_parser().parse_args(["slide.png", "--custom-vectors", "0.6,0.7,0.3",
                                      "0.1,0.9,0.1", "--stain-names", "../escape"])
    with pytest.raises(ValueError):
        resolve_stain_setup(args)
