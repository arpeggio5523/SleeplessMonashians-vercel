"""
sdoc/llm/amend.py — draft the amendment request an operator would send.

The pipeline finds a discrepancy and stops. The operator's actual next action
is to email the counterparty asking for the draft Bill of Lading to be
corrected. This writes that email.

WHY THIS IS SAFE
    The discrepancy is established deterministically before the model is
    called. The model never decides whether two values differ — it only
    writes prose about a fact already settled by `compare.py`, and a human
    reads it before anything is sent. There is no path by which it can
    affect defect precision.

DEGRADES WITHOUT THE MODEL
    If Gemini is unavailable, a plain template is used instead. The button
    always works; only the wording gets less fluent.

USAGE
    from sdoc.llm.amend import draft_amendment
    draft = draft_amendment(result)        # an EmailResult with status MISMATCH
    draft["subject"], draft["body"], draft["source"]   # "llm" | "template"
"""
from __future__ import annotations

import re
from typing import Any, Optional

from . import gemini

FIELD_LABELS = {
    "shipper": "Shipper",
    "consignee": "Consignee",
    "notify_party": "Notify Party",
    "port_of_loading": "Port of Loading",
    "port_of_discharge": "Port of Discharge",
    "container_count": "Container Count",
    "gross_weight_kg": "Gross Weight (kg)",
}


# --------------------------------------------------------------------------
# the facts, already settled by compare.py
# --------------------------------------------------------------------------

def _discrepancies(result) -> list[dict[str, Any]]:
    out = []
    for c in result.comparisons:
        if c.status != "mismatch":
            continue
        out.append({
            "field": c.field,
            "label": FIELD_LABELS.get(c.field, c.field.replace("_", " ")),
            "si": c.si.raw,
            "bl": c.bl.raw,
            "si_source": f"{c.si.source.file.split('/')[-1]} line {c.si.source.line}",
            "bl_source": f"{c.bl.source.file.split('/')[-1]} line {c.bl.source.line}",
        })
    return out


def _reference(result, email: Optional[dict] = None) -> str:
    """
    A booking or B/L reference we can quote, or "". Never invented.

    Field snippets only ever contain their own line, so the reference has to
    come from the email subject, which carries the carrier booking code in a
    recognisable shape: "CMA(SIJ4216073)".
    """
    subject = (email or {}).get("subject", "") or ""
    m = re.search(r"\(([A-Z]{2,4}\d{5,})\)", subject)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{3,4}\d{7,})\b", subject)
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# fallback: no model needed
# --------------------------------------------------------------------------

def _template(result, discrepancies: list[dict], ref: str = "") -> dict[str, str]:
    lines = [
        f"- {d['label']}: the Shipping Instruction states {d['si']}, "
        f"the draft Bill of Lading states {d['bl']}."
        for d in discrepancies
    ]
    subject = ("Amendment required to draft Bill of Lading"
               + (f" — {ref}" if ref else ""))
    body = (
        "Dear Sir or Madam,\n\n"
        "We have checked the draft Bill of Lading"
        + (f" ({ref})" if ref else "")
        + " against the Shipping Instruction and found the following "
          "discrepancies:\n\n"
        + "\n".join(lines)
        + "\n\nThe Shipping Instruction is the authoritative reference. "
          "Please amend the draft accordingly and return it for checking "
          "before finalisation.\n\n"
          "Kind regards,\nShipping Operations"
    )
    return {"subject": subject, "body": body, "source": "template"}


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

PROMPT = """\
You are a shipping operations officer writing to a counterparty about errors
found in a draft Bill of Lading.

The Shipping Instruction is the authoritative reference. The draft Bill of
Lading must be amended to match it.

{reference_line}
Discrepancies found:
{discrepancies}

Write a short, courteous, professional email requesting amendment.

Rules:
- State every discrepancy, with both values, exactly as given above.
- Invent nothing. No dates, no vessel names, no reference numbers, no
  contact names beyond what appears above.
- No placeholders such as [Name] or [Company].
- Sign off as "Shipping Operations".
- Six sentences at most in the body.

Reply with JSON only:
{{"subject": "<one line>", "body": "<the email, plain text, \\n for newlines>"}}
"""


def draft_amendment(result, email: Optional[dict] = None) -> Optional[dict[str, str]]:
    """
    Draft an amendment request for a MISMATCH result.

    result : an EmailResult with status MISMATCH
    email  : the original email record, if available - only used to quote a
             booking reference from the subject

    Returns {"subject", "body", "source"} where source is "llm" or
    "template", or None when the email has no confirmed discrepancy.
    """
    if result.status != "MISMATCH":
        return None
    discrepancies = _discrepancies(result)
    if not discrepancies:
        return None

    ref = _reference(result, email)
    lines = "\n".join(
        f"- {d['label']}: Shipping Instruction = {d['si']} | "
        f"draft Bill of Lading = {d['bl']}"
        for d in discrepancies
    )
    prompt = PROMPT.format(
        reference_line=f"Reference: {ref}\n" if ref else "",
        discrepancies=lines,
    )

    key = gemini._cache_key("amend\x00" + prompt)
    hit = gemini._cache_get(key)
    if hit and hit.get("body"):
        return {"subject": hit["subject"], "body": hit["body"],
                "source": hit.get("source", "llm")}

    if gemini.MODE != "live":
        return _template(result, discrepancies, ref)

    try:
        data = gemini._parse_json(gemini._call(prompt, max_tokens=2048))
    except Exception as exc:
        print(f"  [amend] {result.email_id}: {exc}")
        return _template(result, discrepancies, ref)

    if not isinstance(data, dict) or not data.get("body"):
        return _template(result, discrepancies, ref)

    draft = {
        "subject": str(data.get("subject", ""))[:200]
                   or "Amendment required to draft Bill of Lading",
        "body": str(data["body"])[:4000],
        "source": "llm",
    }
    gemini._cache_put(key, {**draft, "email_id": result.email_id})
    return draft