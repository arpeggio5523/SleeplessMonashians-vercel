"""
Tests for the comparison and escalation rules.

The property being protected here: an unreadable or missing value must
never be reported as a discrepancy. That is what keeps false-alarm rate
near zero, and the brief singles it out.
"""
from sdoc.core.compare import compare_field, decide
from sdoc.core.contract import (CONFIDENCE_THRESHOLD, DocumentExtract,
                                ExtractedField, FieldComparison)


def doc(**fields) -> DocumentExtract:
    """Build a DocumentExtract from {field: (value, confidence)}."""
    d = DocumentExtract()
    for name, spec in fields.items():
        value, conf = spec if isinstance(spec, tuple) else (spec, 0.95)
        d.fields[name] = ExtractedField(value=value, raw=str(value), confidence=conf)
    return d


# ------------------------------------------------------------------ verdicts
def test_equal_trusted_values_match():
    c = compare_field("container_count", doc(container_count=3), doc(container_count=3))
    assert c.status == "match"


def test_different_trusted_values_mismatch():
    c = compare_field("container_count", doc(container_count=3), doc(container_count=4))
    assert c.status == "mismatch"
    assert c.si.value == 3 and c.bl.value == 4


def test_missing_value_is_uncertain_not_mismatch():
    """An absent value is not evidence of a discrepancy."""
    c = compare_field("gross_weight_kg", doc(gross_weight_kg=22000), doc())
    assert c.status == "uncertain"
    assert "BL" in c.reason


def test_missing_in_si_reports_si():
    c = compare_field("shipper", doc(), doc(shipper="ACME"))
    assert c.status == "uncertain" and "SI" in c.reason


def test_low_confidence_is_uncertain_even_when_different():
    """Values differ, but one was read too poorly to trust the difference."""
    low = CONFIDENCE_THRESHOLD - 0.1
    c = compare_field("shipper", doc(shipper=("ACME", low)), doc(shipper="UMBRELLA"))
    assert c.status == "uncertain"
    assert "confidence" in c.reason


def test_both_missing_is_uncertain():
    assert compare_field("notify_party", doc(), doc()).status == "uncertain"


# ------------------------------------------------------------------ decision
def cmp(field, status, reason=None):
    return FieldComparison(field, status, reason=reason)


def test_all_match_is_ok():
    status, reason = decide([cmp(f, "match") for f in ("shipper", "consignee")])
    assert status == "OK" and reason is None


def test_any_mismatch_is_mismatch():
    status, reason = decide([cmp("shipper", "match"),
                             cmp("container_count", "mismatch")])
    assert status == "MISMATCH" and reason is None


def test_uncertainty_outranks_mismatch():
    """
    A partial report is worse than asking a human. If any field could not be
    read, escalate the whole email rather than reporting only what was legible.
    """
    status, reason = decide([cmp("container_count", "mismatch"),
                             cmp("gross_weight_kg", "uncertain",
                                 "value not found in the BL")])
    assert status == "NEEDS_REVIEW"
    assert reason == "missing_value"


def test_low_confidence_reason_is_distinguished():
    status, reason = decide([cmp("shipper", "uncertain",
                                 "extracted with low confidence")])
    assert status == "NEEDS_REVIEW" and reason == "low_confidence"
