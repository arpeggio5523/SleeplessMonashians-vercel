"""
extract.py — document text -> the seven fields, each with confidence
and provenance.

Owner: I (intelligence).

Three tiers, tried in order, with confidence reflecting how the value was
found. Anything below contract.CONFIDENCE_THRESHOLD is escalated rather
than compared, which is what keeps false-alarm rate near zero.

    tier 1  'Label: value'          confidence 0.95
    tier 2  'Label    value'        confidence 0.85   (wide column layout)
    tier 3  'Label value'           confidence 0.70   (tight pdfplumber layout)
    tier 4  LLM fallback            confidence from the model, capped 0.80

The label list is closed — pools.py in the generator emits nothing else —
so tiers 1-3 cover the supplied dataset. The LLM tier exists for labels
outside that list, which is what makes the system survive rephrased inputs.
"""
from __future__ import annotations

import re
from typing import Optional

from .contract import FIELDS, DocumentExtract, ExtractedField, Source
from .ingest import strip_non_ascii
from .normalize import is_blank, normalize

# Every label variant the data can contain, ordered most specific first so
# 'TOTAL Gross Weight (KG)' is tried before bare 'Gross Weight'.
LABELS: dict[str, list[str]] = {
    "shipper": [
        "Shipper/Exporter", "Shipper (Principal or Seller)", "Shipper", "SHIPPER",
    ],
    "consignee": [
        "Consignee (Non-Negotiable)", "To the Order of", "Consignee", "CONSIGNEE",
    ],
    "notify_party": [
        "Notify Party/Intermediate Consignee", "Notify Party", "NOTIFY PARTY", "Notify",
    ],
    "port_of_loading": [
        "Port of Loading (POL)", "PORT OF LOADING", "Port of Loading",
        "Load Port", "POL",
    ],
    "port_of_discharge": [
        "Port of Discharge (POD)", "PORT OF DISCHARGE", "Port of Discharge",
        "Discharge Port", "POD",
    ],
    "container_count": [
        "No. of Containers or Packages", "No. of Containers",
        "Total Containers", "Container Count",
    ],
    "gross_weight_kg": [
        "TOTAL Gross Weight (KG)", "TOTAL Gross Wt (kgs)", "Gross Weight (KG)",
        "Gross Wt (kgs)", "GROSS WEIGHT", "Gross Weight",
    ],
}

# Which document is this? Used to catch the wrong_doc_type escalation.
SI_MARKERS = ("SHIPPING INSTRUCTION", "BL INSTRUCTION", "BILL OF LADING INSTRUCTION")
BL_MARKERS = ("BILL OF LADING",)
OTHER_MARKERS = ("COMMERCIAL INVOICE", "PACKING LIST", "CERTIFICATE OF ORIGIN",
                 "ARRIVAL NOTICE", "DELIVERY ORDER")

CONF_COLON, CONF_WIDE, CONF_WRAP, CONF_TIGHT = 0.95, 0.85, 0.80, 0.70

# Every label string we know about, for detecting when a "value" captured by a
# loose pattern is really just the tail of a longer label.
ALL_LABELS = tuple(sorted({l.upper() for labs in LABELS.values() for l in labs},
                          key=len, reverse=True))


def _is_label_fragment(label: str, captured: str) -> bool:
    """
    True when 'label captured' reconstructs a longer known label.

    In wide PDF columns a long label can occupy the whole line, e.g.

        Notify Party/Intermediate Consignee
                                     CERIEX

    A loose pattern then matches the short label 'Notify' and captures
    'Party/Intermediate Consignee' as if it were a company name, producing a
    confident, entirely fabricated mismatch.
    """
    joined = f"{label} {captured}".upper().strip()
    return any(known.startswith(joined) or joined.startswith(known)
               for known in ALL_LABELS if len(known) > len(label))


def detect_doc_type(text: str) -> str:
    head = text[:500].upper()
    for m in OTHER_MARKERS:
        if m in head:
            return "OTHER"
    for m in SI_MARKERS:
        if m in head:
            return "SI"
    for m in BL_MARKERS:
        if m in head:
            return "BL"
    return "UNKNOWN"


def _patterns(label: str) -> list[tuple[re.Pattern, float]]:
    esc = re.escape(label)
    # optional TOTAL prefix; then up to 4 characters of glyph noise; then an
    # optional parenthetical; then the separator.
    #
    # The noise allowance matters. Documents carry bilingual labels such as
    # "Gross Weight<CJK>(KGS):". Different PDF extractors render unmappable
    # glyphs differently: poppler emits non-ASCII placeholders (stripped by
    # strip_non_ascii), while pdfplumber substitutes ASCII letters such as
    # "nn", which survive and break an exact label match. Allowing a few
    # junk characters makes the match extractor-independent.
    head = (r"^\s*(?:TOTAL\s+)?" + esc + r"[^\s:\uff1a]{0,4}"
            r"\s*(?:\([^)]*\))?\s*")
    return [
        (re.compile(head + r"[::]\s*(\S.*)$", re.I), CONF_COLON),
        (re.compile(head + r"\s{2,}(\S.*)$", re.I), CONF_WIDE),
        (re.compile(head + r"\s+(\S.*)$", re.I), CONF_TIGHT),
    ]


def _alone_on_line(label: str) -> re.Pattern:
    """Label occupying a whole line, with its value wrapped to the next."""
    return re.compile(r"^\s*(?:TOTAL\s+)?" + re.escape(label) +
                      r"\s*(?:\([^)]*\))?\s*[::]?\s*$", re.I)


def extract_field(field: str, lines: list[str], path: str) -> ExtractedField:
    """
    Find one field. Returns an empty ExtractedField when not found, or when
    the document explicitly leaves it blank.

    Important: if a label is found but its value is a placeholder ('TBA',
    '____MT'), we stop looking for this field entirely rather than falling
    through to a looser pattern. Otherwise a looser pattern re-matches the
    same line and captures fragments like '(POD): TBA' as if they were real,
    which produces a false discrepancy.
    """
    for label in LABELS[field]:
        # Label alone on its line: the value wrapped to the following line.
        alone = _alone_on_line(label)
        for idx, line in enumerate(lines):
            if not alone.match(strip_non_ascii(line)):
                continue
            for nxt in range(idx + 1, min(idx + 3, len(lines))):
                cand = strip_non_ascii(lines[nxt])
                if not cand.strip():
                    continue
                if not lines[nxt][:1].isspace():   # must be an indented continuation
                    break
                raw = cand.strip()
                if is_blank(raw):
                    break
                value = normalize(field, raw)
                if value is None:
                    break
                return ExtractedField(
                    value=value, raw=raw, confidence=CONF_WRAP, method="rule",
                    source=Source(file=path, line=nxt + 1, label_seen=label,
                                  snippet=lines[nxt].strip()[:200]),
                )
            break

        for pattern, conf in _patterns(label):
            for idx, line in enumerate(lines):
                ascii_line = strip_non_ascii(line)
                m = pattern.match(ascii_line)
                if not m:
                    continue
                raw = m.group(1).strip()
                if raw.startswith(("|", ":")):
                    continue
                if _is_label_fragment(label, raw):
                    continue
                if is_blank(raw):
                    # The document says this field is empty. Believe it.
                    return ExtractedField(
                        raw=raw, confidence=0.0, method="rule",
                        source=Source(file=path, line=idx + 1, label_seen=label,
                                      snippet=line.strip()[:200]),
                    )
                value = normalize(field, raw)
                if value is None:
                    continue
                return ExtractedField(
                    value=value,
                    raw=raw,
                    confidence=conf,
                    method="rule",
                    source=Source(file=path, line=idx + 1,
                                  label_seen=label, snippet=line.strip()[:200]),
                )
    return ExtractedField()


def extract_document(text: str, path: str, ingest_method: str = "text",
                     readable: bool = True,
                     warnings: Optional[list[str]] = None,
                     llm=None) -> DocumentExtract:
    """
    text  : plain text from ingest
    llm   : optional callable(text, missing_fields) -> {field: (value, conf)}
            Owner I wires Gemini in here. Left None, the module is pure rules.
    """
    doc = DocumentExtract(path=path, ingest_method=ingest_method,
                          readable=readable, warnings=list(warnings or []))
    if not readable or not text.strip():
        doc.readable = False
        return doc

    doc.doc_type = detect_doc_type(text)
    lines = [l.rstrip() for l in text.split("\n")]

    for field in FIELDS:
        doc.fields[field] = extract_field(field, lines, path)

    # ---- tier 4: LLM fallback for whatever the rules could not find -----
    missing = [f for f in FIELDS if not doc.fields[f].present]
    if missing and llm is not None:
        try:
            guesses = llm(text, missing) or {}
            for f, (raw, conf) in guesses.items():
                if f not in FIELDS or is_blank(raw):
                    continue
                value = normalize(f, raw)
                if value is None:
                    continue
                doc.fields[f] = ExtractedField(
                    value=value, raw=str(raw),
                    confidence=min(float(conf), 0.80),   # never outrank a rule
                    method="llm",
                    source=Source(file=path, line=-1, label_seen="(model)",
                                  snippet="recovered by language model"),
                )
        except Exception as e:
            doc.warnings.append(f"llm fallback failed: {e}")

    still_missing = [f for f in FIELDS if not doc.fields[f].present]
    if still_missing:
        doc.warnings.append("fields not found: " + ", ".join(still_missing))
    return doc