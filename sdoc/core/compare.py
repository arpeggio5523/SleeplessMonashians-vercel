"""
compare.py — two DocumentExtracts -> per-field verdicts, and the decision
about whether a human is needed.

Owner: P (pipeline lead).

The rule that matters most, from the brief: a value that could not be read
is NOT a discrepancy. Conflating "unreadable" with "different" is what
produces false alarms, and the brief is explicit that accuracy means
"identifying the right requests and the right discrepancies without
creating false alarms".

    both present, both trusted, equal        -> match
    both present, both trusted, different    -> MISMATCH
    either absent                            -> uncertain (missing_value)
    either below confidence threshold        -> uncertain (low_confidence)
"""
from __future__ import annotations

from typing import Optional

from .contract import FIELDS, DocumentExtract, FieldComparison


def compare_field(field: str, si: DocumentExtract,
                  bl: DocumentExtract) -> FieldComparison:
    a, b = si.get(field), bl.get(field)

    if not a.present or not b.present:
        which = "SI" if not a.present else "BL"
        return FieldComparison(field, "uncertain", a, b,
                               reason=f"value not found in the {which}")

    if not a.trusted or not b.trusted:
        return FieldComparison(field, "uncertain", a, b,
                               reason="extracted with low confidence")

    if a.value == b.value:
        return FieldComparison(field, "match", a, b)

    return FieldComparison(field, "mismatch", a, b)


def compare_documents(si: DocumentExtract,
                      bl: DocumentExtract) -> list[FieldComparison]:
    return [compare_field(f, si, bl) for f in FIELDS]


def decide(comparisons: list[FieldComparison]) -> tuple[str, Optional[str]]:
    """
    Turn per-field verdicts into one status for the email.

    Returns (status, review_reason).

    Note the ordering: uncertainty wins over mismatch. If any field could
    not be read we escalate the whole email rather than reporting a partial
    comparison, because a report that silently omits a field is worse than
    one that says "a human should look at this".
    """
    uncertain = [c for c in comparisons if c.status == "uncertain"]
    if uncertain:
        low_conf = any("confidence" in (c.reason or "") for c in uncertain)
        return "NEEDS_REVIEW", ("low_confidence" if low_conf else "missing_value")

    if any(c.status == "mismatch" for c in comparisons):
        return "MISMATCH", None

    return "OK", None
