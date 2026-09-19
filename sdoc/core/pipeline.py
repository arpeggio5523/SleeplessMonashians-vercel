"""
pipeline.py — orchestration. The only module that knows the full sequence.

Owner: P (pipeline lead).

    classify -> ingest -> extract -> compare -> decide -> EmailResult

The data source is abstracted behind EmailSource so the pipeline does not
care whether records come from a folder, the scoring server, or eventually
a real mailbox. That abstraction is what lets the roadmap slide say
"swap the loader for a Graph API poller; the pipeline is unchanged".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Protocol

from .classify import classify
from .compare import compare_documents, decide
from .contract import Classification, EmailResult
from .extract import extract_document
from .ingest import ingest


# --------------------------------------------------------------------------
# data source
# --------------------------------------------------------------------------

class EmailSource(Protocol):
    def emails(self) -> Iterable[dict]: ...
    def attachment(self, path: str) -> Optional[bytes]: ...


class FolderSource:
    """Reads the supplied bundle from disk."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def emails(self):
        for p in sorted((self.root / "inbox").glob("email_*.json")):
            yield json.loads(p.read_text(encoding="utf-8"))

    def attachment(self, path: str) -> Optional[bytes]:
        p = self.root / path
        return p.read_bytes() if p.exists() else None


# --------------------------------------------------------------------------
# escalation that happens before any document is opened
# --------------------------------------------------------------------------

def _attachment_check(email: dict) -> Optional[str]:
    """
    Distinguishes two cases that look identical in metadata and differ only
    in the body:

      "please assist to send the draft BL for checking"   -> the BL does not
          exist yet. Nothing to compare. Not an escalation.

      "please compare the SI and draft BL ... (attachments appear to have
          been dropped)"  -> documents were expected. Escalate.
    """
    attachments = email.get("attachments") or []
    if len(attachments) >= 2:
        return None
    body = " ".join((email.get("body") or "").split()).upper()
    if "COMPARE THE SI" in body:
        return "missing_attachment"
    return None


# --------------------------------------------------------------------------
# main entry point
# --------------------------------------------------------------------------

def process_email(email: dict, source: EmailSource,
                  llm_classify=None, llm_extract=None) -> EmailResult:
    eid = email["email_id"]
    cls: Classification = classify(email, llm=llm_classify)
    result = EmailResult(email_id=eid, classification=cls)

    # Only comparison requests continue past classification.
    if cls.category != "BL_COMPARISON":
        return result

    reason = _attachment_check(email)
    if reason:
        result.status, result.review_reason = "NEEDS_REVIEW", reason
        result.notes.append("A comparison was requested but the documents were not attached.")
        return result

    attachments = email.get("attachments") or []
    if len(attachments) < 2:
        result.notes.append("No draft BL supplied yet; nothing to compare.")
        return result

    si_path, bl_path = attachments[0], attachments[1]
    si_in = ingest(si_path, source.attachment(si_path))
    bl_in = ingest(bl_path, source.attachment(bl_path))

    result.si = extract_document(si_in.text, si_path, si_in.method,
                                 si_in.readable, si_in.warnings, llm=llm_extract)
    result.bl = extract_document(bl_in.text, bl_path, bl_in.method,
                                 bl_in.readable, bl_in.warnings, llm=llm_extract)

    if not result.si.readable or not result.bl.readable:
        result.status, result.review_reason = "NEEDS_REVIEW", "unreadable"
        which = "SI" if not result.si.readable else "BL"
        result.notes.append(f"The {which} could not be read. It may be a scanned image.")
        return result

    if "OTHER" in (result.si.doc_type, result.bl.doc_type):
        result.status, result.review_reason = "NEEDS_REVIEW", "wrong_doc_type"
        result.notes.append("An attachment is not a Shipping Instruction or Bill of Lading.")
        return result

    result.comparisons = compare_documents(result.si, result.bl)
    result.status, result.review_reason = decide(result.comparisons)

    if result.status == "MISMATCH":
        names = ", ".join(result.defect_fields)
        result.notes.append(f"Discrepancy found in: {names}.")
    elif result.status == "OK":
        result.notes.append("No mismatch detected.")

    return result


def run(source: EmailSource, llm_classify=None,
        llm_extract=None) -> dict[str, EmailResult]:
    return {
        e["email_id"]: process_email(e, source, llm_classify, llm_extract)
        for e in source.emails()
    }


def to_submission(results: dict[str, EmailResult]) -> dict[str, dict]:
    """The narrow shape the official scorer reads."""
    return {eid: r.to_submission() for eid, r in results.items()}
