"""
classify.py — email record -> one of five categories, with confidence.

Owner: I (intelligence).

Read the BODY, not the subject. Subjects in this dataset are deliberately
misleading: a GENERAL email is titled '_Reminder_Paper - Submit SI & AED'
while its body is a berthing report. Subject-first scored macro-F1 0.56;
body-first scores 0.97.

Confidence tiers:
    0.95  a distinctive body phrase matched
    0.75  a weaker signal (attachments present, generic keyword)
    <=0.50 nothing matched — this is where the LLM fallback should fire
"""
from __future__ import annotations

from typing import Optional

from .contract import Classification

STRONG = 0.95
WEAK = 0.75
GUESS = 0.40

# Ordered: the first match wins, so put the most specific phrases first.
RULES: list[tuple[str, tuple[str, ...], float]] = [
    ("BL_COMPARISON", (
        "PLEASE COMPARE THE SI AND DRAFT BL",
        "SEND THE DRAFT BL",
        "DRAFT BL FOR",
    ), STRONG),
    ("SI_REQUEST", (
        "PLEASE FIND SHIPPING INSTRUCTION",
        "SHIPPING INSTRUCTION FOR",
    ), STRONG),
    ("INVOICE_QUERY", (
        "QUERY ON INVOICE",
        "DETENTION CHARGES",
        "GR IS STILL MISSING",
        "D&D",
    ), STRONG),
    ("GENERAL", (
        "OUTSTANDING BL",
        "BERTHING REPORT",
        "SUBMIT SI & AED",
        "UPDATE SUMMARY",
        "LOADING COMPLETED",
        "PENDING ITEMS",
    ), STRONG),
    ("SPAM", (
        "CONGRATULAT", "PRIZE", "CLAIM YOUR", "MAILBOX HAS EXCEEDED",
        "VERIFY YOUR ACCOUNT", "LIMITED TIME OFFER", "UNPAID CUSTOMS",
        "BITCOIN", "GIFT CARD", "CLICK HERE", "HTTP://", "GUARANTEED",
    ), STRONG),
    # Weaker signal, deliberately narrow. Do NOT widen this to BILLING /
    # DEBIT NOTE / CREDIT NOTE — those appear in GENERAL operational updates
    # and cost 15 GENERAL emails when tried.
    ("INVOICE_QUERY", ("INVOICE",), WEAK),
]


def classify(email: dict, llm=None) -> Classification:
    """
    email : {'email_id', 'subject', 'body', 'attachments', ...}
    llm   : optional callable(email) -> (category, confidence).
            Owner I wires Gemini here; it fires only when rules are unsure,
            so the common path stays fast, free and deterministic.
    """
    body = " ".join((email.get("body") or "").split()).upper()

    for category, phrases, conf in RULES:
        for phrase in phrases:
            if phrase in body:
                return Classification(category, conf, "rule", phrase)

    # Weak structural signal: attachments on an unrecognised body.
    if email.get("attachments"):
        return Classification("BL_COMPARISON", WEAK, "rule", "has attachments")

    # ---- fallback -------------------------------------------------------
    # TODO(I): this is where the 7 SPAM-read-as-GENERAL errors live. They use
    # no distinctive vocabulary. Do NOT fix by adding their literal strings —
    # that overfits to the 520 emails we can see. Let the model decide.
    if llm is not None:
        try:
            category, conf = llm(email)
            return Classification(category, min(float(conf), 0.80), "llm", "model")
        except Exception:
            pass

    return Classification("GENERAL", GUESS, "rule", "no signal matched")
