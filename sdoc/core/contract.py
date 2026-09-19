"""
contract.py — THE FROZEN INTERFACE. Do not change without telling the team.

Every stage of the pipeline speaks in these shapes. As long as a module
takes and returns these, its internals can be swapped freely: rules can
become an LLM call, pdfplumber can become Document AI, and nothing
downstream notices.

Owner: P (pipeline lead). Changes go through P only.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal, Optional

# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------

FIELDS: tuple[str, ...] = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)

CATEGORIES: tuple[str, ...] = (
    "BL_COMPARISON",
    "SI_REQUEST",
    "INVOICE_QUERY",
    "GENERAL",
    "SPAM",
)

# review_reason values the scorer recognises
REVIEW_REASONS: tuple[str, ...] = (
    "missing_attachment",   # comparison asked for, documents absent
    "unreadable",           # attachment present but no text could be recovered
    "wrong_doc_type",       # not an SI/BL pair (invoice, packing list, ...)
    "missing_value",        # a required field is blank or unparseable
    "low_confidence",       # extracted, but not confidently enough to judge
)

Method = Literal["rule", "llm", "ocr", "vision"]
Status = Literal["OK", "MISMATCH", "NEEDS_REVIEW"]
FieldStatus = Literal["match", "mismatch", "uncertain"]

# Below this, a field is not trusted enough to call a mismatch on.
# Tune empirically; record the chosen value and why in the deck.
CONFIDENCE_THRESHOLD = 0.60


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------

@dataclass
class Source:
    """Where a value came from. Shown in the UI next to every value."""
    file: str = ""
    line: int = -1
    label_seen: str = ""      # the literal label text matched in the document
    snippet: str = ""         # the full source line, for display

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedField:
    """One field pulled out of one document."""
    value: Any = None                    # normalised, comparable value
    raw: Optional[str] = None            # exactly as it appeared
    confidence: float = 0.0
    method: Method = "rule"
    source: Source = field(default_factory=Source)

    @property
    def present(self) -> bool:
        return self.value is not None

    @property
    def trusted(self) -> bool:
        return self.present and self.confidence >= CONFIDENCE_THRESHOLD

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.to_dict()
        return d


@dataclass
class DocumentExtract:
    """Everything recovered from one attachment."""
    path: str = ""
    doc_type: Literal["SI", "BL", "OTHER", "UNKNOWN"] = "UNKNOWN"
    ingest_method: str = "text"          # text | pdf | docx | xlsx | ocr
    readable: bool = True
    fields: dict[str, ExtractedField] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def get(self, name: str) -> ExtractedField:
        return self.fields.get(name, ExtractedField())

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "doc_type": self.doc_type,
            "ingest_method": self.ingest_method,
            "readable": self.readable,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "warnings": list(self.warnings),
        }


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------

@dataclass
class FieldComparison:
    """One field, SI against BL, with the evidence for the verdict."""
    field: str
    status: FieldStatus
    si: ExtractedField = field(default_factory=ExtractedField)
    bl: ExtractedField = field(default_factory=ExtractedField)
    reason: Optional[str] = None         # why uncertain, when uncertain

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "status": self.status,
            "si": self.si.to_dict(),
            "bl": self.bl.to_dict(),
            "reason": self.reason,
        }


@dataclass
class Classification:
    category: str
    confidence: float = 1.0
    method: Method = "rule"
    evidence: str = ""                   # the text that triggered the decision

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EmailResult:
    """The full result for one email. This is what the UI renders."""
    email_id: str
    classification: Classification
    status: Status = "OK"
    review_reason: Optional[str] = None
    comparisons: list[FieldComparison] = field(default_factory=list)
    si: Optional[DocumentExtract] = None
    bl: Optional[DocumentExtract] = None
    notes: list[str] = field(default_factory=list)

    # ---- derived -------------------------------------------------------
    @property
    def defect_fields(self) -> list[str]:
        return sorted(c.field for c in self.comparisons if c.status == "mismatch")

    @property
    def has_defect(self) -> bool:
        return self.status == "MISMATCH"

    @property
    def needs_review(self) -> bool:
        return self.status == "NEEDS_REVIEW"

    # ---- serialisation -------------------------------------------------
    def to_submission(self) -> dict:
        """The narrow shape the official scorer reads."""
        return {
            "category": self.classification.category,
            "status": self.status,
            "review_reason": self.review_reason,
            "has_defect": self.has_defect,
            "defect_fields": self.defect_fields,
        }

    def to_dict(self) -> dict:
        """The full shape the API and UI use."""
        return {
            "email_id": self.email_id,
            "classification": self.classification.to_dict(),
            "status": self.status,
            "review_reason": self.review_reason,
            "has_defect": self.has_defect,
            "defect_fields": self.defect_fields,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "si": self.si.to_dict() if self.si else None,
            "bl": self.bl.to_dict() if self.bl else None,
            "notes": list(self.notes),
        }
