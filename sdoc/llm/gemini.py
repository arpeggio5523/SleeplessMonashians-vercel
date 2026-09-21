"""
sdoc/llm/gemini.py — Gemini fallback for cases the rules can't settle.

Uses the current `google-genai` SDK (`from google import genai`).
The older `google-generativeai` package is deprecated and its models are
being retired, so do not reinstate it.

    pip install google-genai

WHEN THIS RUNS
    Rules settle 493 of 520 emails at confidence 0.75-0.95 and return
    immediately. Only the 27 where no rule matched reach this module, so a
    full run costs ~27 calls and re-runs cost zero (results are cached).

WHY IT EXISTS
    Not to squeeze the score. The rules match literal phrases, so a reworded
    email falls straight through. This is the safety net that makes the
    system survive inputs it has not seen.

USAGE
    from sdoc.llm.gemini import classify_email
    results = run(source, llm_classify=classify_email)

ENVIRONMENT
    GEMINI_API_KEY      required for live mode
    SDOC_GEMINI_MODEL   override the model (default below)
    SDOC_LLM_MODE       live | mock | off
    SDOC_LLM_CACHE      cache directory (default .cache/llm)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

# Google retires models on a rolling basis. If this one 404s, the API error
# names its replacement — set SDOC_GEMINI_MODEL to that, or to the floating
# alias "gemini-flash-latest".
# Flash-Lite, deliberately. The full Flash models allow roughly 20 free
# requests per day; Flash-Lite allows roughly 500. Measured on this task the
# two are indistinguishable - both give macro-F1 0.9982 and fix the same 7
# emails - so the larger model buys nothing and exhausts its quota in one
# run. Override with SDOC_GEMINI_MODEL if a model is ever retired.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

MODEL = os.environ.get("SDOC_GEMINI_MODEL", DEFAULT_MODEL)
MODE = os.environ.get("SDOC_LLM_MODE", "live")          # live | mock | off
CACHE_DIR = Path(os.environ.get("SDOC_LLM_CACHE", ".cache/llm"))
MAX_RETRIES = 6

# Pace ourselves rather than firing every request at once and eating a string
# of 429s. 15/min suits Flash-Lite; drop to 5 if you switch to a full Flash
# model, which is stricter.
RPM = int(os.environ.get("SDOC_LLM_RPM", "15"))
MIN_INTERVAL = 60.0 / max(RPM, 1)

# Combined budget for thinking + answer. The reply is ~30 tokens, but Gemini 3
# spends tokens reasoning first, so this must be generous or the JSON arrives
# truncated. 1024 is ample for a one-line classification.
MAX_OUTPUT_TOKENS = 1024

CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")

# The SDK prints an automatic-function-calling advisory on every call. We
# never use function calling, so it is pure noise.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

_client = None
_last_call = 0.0
_daily_exhausted = False
_stats = {"cache_hits": 0, "calls": 0, "failures": 0, "throttled_s": 0.0}


def _throttle() -> None:
    """Keep at least MIN_INTERVAL between calls. Cheaper than eating 429s."""
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        _stats["throttled_s"] += wait
        time.sleep(wait)
    _last_call = time.monotonic()


def _retry_after(msg: str) -> Optional[float]:
    """The API tells us exactly how long to wait. Believe it."""
    m = re.search(r"retry in ([\d.]+)s", msg, re.I)
    if m:
        return float(m.group(1)) + 1.0
    m = re.search(r"'retryDelay':\s*'(\d+)s'", msg)
    if m:
        return float(m.group(1)) + 1.0
    return None


# --------------------------------------------------------------------------
# cache — keyed by prompt content, so editing the prompt invalidates it
# --------------------------------------------------------------------------

def _cache_key(payload: str) -> str:
    """
    Keyed on the PROMPT only, not the model. Free-tier daily quotas are
    per-model, so switching models is the normal way to keep working — and
    answers already paid for should survive that switch.
    """
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def _legacy_key(payload: str) -> str:
    """Pre-existing entries written when the key included the model name."""
    return hashlib.sha256((MODEL + "\x00" + payload).encode()).hexdigest()[:20]


def _cache_get(key: str, legacy: Optional[str] = None) -> Optional[dict]:
    for k in (key, legacy):
        if not k:
            continue
        p = CACHE_DIR / f"{k}.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def _cache_put(key: str, value: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps(value, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------

def _get_client():
    global _client
    if _client is None:
        try:
            from google import genai
        except ImportError as e:
            raise RuntimeError(
                "google-genai not installed. Run:  pip install google-genai\n"
                "(the old google-generativeai package is deprecated)") from e
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. PowerShell:  $env:GEMINI_API_KEY='...'")
        _client = genai.Client(api_key=key)
    return _client


def _config(
    max_tokens: int = MAX_OUTPUT_TOKENS,
    temperature: float = 0.0,
):
    """
    JSON-only configuration with controllable temperature.

    Classification keeps the default temperature of 0.0 for deterministic
    behaviour. Other callers, such as amendment regeneration, may explicitly
    request a higher temperature for wording variation.

    Two Gemini quirks matter here:

    1. max_output_tokens is a COMBINED budget for thinking tokens AND the
       answer. A small cap makes the model burn the whole budget thinking
       and return a truncated fragment like '{"ok'. Keep it generous.
    2. Gemini 3.x uses thinking_level; Gemini 2.5 uses thinking_budget.
       Passing both to a 3.x model is an error, so pick by model family.
       'minimal' is the right level for classification.
    """
    try:
        from google.genai import types
        if "2.5" in MODEL or "2.0" in MODEL:
            thinking = types.ThinkingConfig(thinking_budget=0)
        else:
            thinking = types.ThinkingConfig(thinking_level="minimal")
        return types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            thinking_config=thinking,
        )
    except Exception:
        # older/newer SDK without ThinkingConfig, or an unsupported level
        try:
            from google.genai import types
            return types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            )
        except Exception:
            return {"temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json"}


def _truncated(resp) -> bool:
    try:
        return str(resp.candidates[0].finish_reason).upper().endswith("MAX_TOKENS")
    except Exception:
        return False


def _call(
    prompt: str,
    max_tokens: int = MAX_OUTPUT_TOKENS,
    temperature: float = 0.0,
) -> str:
    """One call, with backoff on rate limits and one retry on truncation."""
    client = _get_client()
    delay = 5.0
    budget = max_tokens
    for attempt in range(MAX_RETRIES):
        try:
            _throttle()
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=_config(budget, temperature=temperature),
            )
            _stats["calls"] += 1
            text = getattr(resp, "text", "") or ""
            if (_truncated(resp) or not text.strip()) and budget < 16384:
                # thinking ate the budget; give it more room once
                budget *= 4
                continue
            return text
        except Exception as e:
            msg = str(e).lower()
            if "not_found" in msg or "no longer available" in msg or "404" in msg:
                # unrecoverable; the API message names the replacement model
                raise RuntimeError(
                    f"Model '{MODEL}' is unavailable. Set SDOC_GEMINI_MODEL to the "
                    f"replacement named below, or to 'gemini-flash-latest'.\n{e}") from e
            global _daily_exhausted
            if "perday" in msg.replace("_", "").replace(" ", "").lower():
                _daily_exhausted = True
                raise RuntimeError(
                    f"Daily free-tier quota for '{MODEL}' is exhausted. "
                    f"Quotas are PER MODEL, so switch to another and re-run:\n"
                    f"  $env:SDOC_GEMINI_MODEL='gemini-2.5-flash'\n"
                    f"Already-cached answers carry over.") from e

            transient = any(w in msg for w in
                            ("429", "rate", "quota", "resource_exhausted",
                             "503", "unavailable", "timeout", "deadline"))
            if transient and attempt < MAX_RETRIES - 1:
                wait = _retry_after(str(e)) or delay
                wait = min(wait, 90.0)
                print(f"  [llm] rate limited, waiting {wait:.0f}s "
                      f"(attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
                delay = min(delay * 2, 60.0)
                continue
            raise
    return ""


def _parse_json(text: str) -> Optional[dict]:
    """Models emit fences, prose, trailing commentary. Take the first object."""
    if not text:
        return None
    text = re.sub(r"^\s*```(?:json)?|```\s*$", "", text.strip(),
                  flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*?\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

PROMPT = """\
You are triaging the shared inbox of a shipping operations team.
Assign the email to exactly one category.

BL_COMPARISON - asks someone to check or compare a Shipping Instruction
  against a draft Bill of Lading, or discusses a draft BL awaiting checking.
SI_REQUEST - supplies or requests a Shipping Instruction for a booking.
INVOICE_QUERY - about an invoice, freight charge, billing, detention or
  demurrage.
GENERAL - routine internal operations: berthing reports, status summaries,
  automated system notifications, holiday notices, reminders.
SPAM - unsolicited commercial mail, phishing, prize or lottery claims,
  advance-fee fraud, crypto offers. Judge intent and sender, not vocabulary:
  scam mail often imitates shipping language.

Weigh the sender's domain. Mail from the company's own domain or a known
partner is operational even when worded oddly. Mail from an unrelated or
throwaway domain making financial or urgent requests is spam.

The subject line may not match the body. When they disagree, trust the body.

Reply with JSON only, no prose:
{{"category": "<one of the five>", "confidence": <0.0-1.0>, "why": "<8 words max>"}}

FROM: {sender}
SUBJECT: {subject}
BODY:
{body}
"""


def classify_email(email: dict) -> tuple[str, float]:
    """
    Called by classify() only when no rule matched.
    Returns (category, confidence). On any failure returns a low-confidence
    GENERAL so the pipeline degrades instead of crashing.
    """
    sender = email.get("from") or "(unknown)"
    subject = (email.get("subject") or "")[:200]
    body = " ".join((email.get("body") or "").split())[:1200]
    prompt = PROMPT.format(sender=sender, subject=subject, body=body)

    key = _cache_key(prompt)
    hit = _cache_get(key, _legacy_key(prompt))
    if hit is not None:
        _stats["cache_hits"] += 1
        return hit["category"], hit["confidence"]

    if MODE == "off":
        return "GENERAL", 0.30
    if MODE == "mock":
        # plumbing test, no API call: internal domain -> operational
        domain = sender.split("@")[-1].lower()
        return ("GENERAL", 0.70) if domain.endswith("aprilasia.com") else ("SPAM", 0.70)

    if _daily_exhausted:
        _stats["failures"] += 1
        return "GENERAL", 0.30

    eid = email.get("email_id", "?")
    n = _stats["calls"] + 1
    print(f"  [llm] {n:>3}  {eid} ...", end="", flush=True)
    try:
        data = _parse_json(_call(prompt))
    except Exception as e:
        _stats["failures"] += 1
        print(f" FAILED\n        {str(e)[:160]}")
        return "GENERAL", 0.30

    if not data or data.get("category") not in CATEGORIES:
        _stats["failures"] += 1
        print(f" bad response: {str(data)[:80]}")
        return "GENERAL", 0.30

    category = data["category"]
    try:
        confidence = max(0.0, min(float(data.get("confidence", 0.7)), 1.0))
    except (TypeError, ValueError):
        confidence = 0.7

    why = str(data.get("why", ""))[:60]
    print(f" {category} ({confidence:.2f}) {why}")

    _cache_put(key, {"category": category, "confidence": confidence,
                     "why": why, "email_id": eid})
    return category, confidence


# --------------------------------------------------------------------------
# batched prefetch — one request for many emails
# --------------------------------------------------------------------------

BATCH_SIZE = int(os.environ.get("SDOC_LLM_BATCH", "15"))

BATCH_PROMPT = """\
You are triaging the shared inbox of a shipping operations team.
Assign EACH email below to exactly one category.

BL_COMPARISON - asks someone to check or compare a Shipping Instruction
  against a draft Bill of Lading, or discusses a draft BL awaiting checking.
SI_REQUEST - supplies or requests a Shipping Instruction for a booking.
INVOICE_QUERY - about an invoice, freight charge, billing, detention or
  demurrage.
GENERAL - routine internal operations: berthing reports, status summaries,
  automated system notifications, holiday notices, reminders.
SPAM - unsolicited commercial mail, phishing, prize or lottery claims,
  advance-fee fraud, crypto offers. Judge intent and sender, not vocabulary:
  scam mail often imitates shipping language.

Weigh the sender's domain. Mail from the company's own domain or a known
partner is operational even when worded oddly. Mail from an unrelated or
throwaway domain making financial or urgent requests is spam.

The subject line may not match the body. When they disagree, trust the body.

Return ONE JSON object per email, keyed by its id. Include EVERY id given.
No prose, no markdown:
{{"<id>": {{"category": "<one of the five>", "confidence": <0.0-1.0>, "why": "<8 words max>"}}, ...}}

EMAILS:
{emails}
"""


def _render(email: dict) -> str:
    sender = email.get("from") or "(unknown)"
    subject = (email.get("subject") or "")[:160]
    body = " ".join((email.get("body") or "").split())[:700]
    return (f"--- id: {email.get('email_id')}\n"
            f"FROM: {sender}\nSUBJECT: {subject}\nBODY: {body}")


def prefetch_classifications(emails: list[dict]) -> int:
    """
    Classify many emails in a few requests instead of one each, and write the
    results into the same cache classify_email() reads.

    Free-tier quotas are per REQUEST, not per email, so 27 emails in 2 batched
    requests costs 2 of your daily allowance rather than 27.

    Anything the batch misses or mangles is simply left uncached — classify_email
    will fall back to a single call for it, or to the rule guess.

    Returns the number of classifications written.
    """
    pending = []
    for e in emails:
        prompt = PROMPT.format(sender=e.get("from") or "(unknown)",
                               subject=(e.get("subject") or "")[:200],
                               body=" ".join((e.get("body") or "").split())[:1200])
        if _cache_get(_cache_key(prompt), _legacy_key(prompt)) is None:
            pending.append((e, prompt))

    if not pending:
        print(f"  [llm] all {len(emails)} already cached")
        return 0
    if MODE != "live":
        return 0

    written = 0
    batches = [pending[i:i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    print(f"  [llm] {len(pending)} uncached -> {len(batches)} batched request(s)")

    for bi, batch in enumerate(batches, 1):
        body = "\n\n".join(_render(e) for e, _ in batch)
        print(f"  [llm] batch {bi}/{len(batches)} ({len(batch)} emails) ...",
              end="", flush=True)
        try:
            raw = _call(BATCH_PROMPT.format(emails=body), max_tokens=8192)
            data = _parse_json(raw)
        except Exception as e:
            print(f" FAILED\n        {str(e)[:160]}")
            continue

        if not isinstance(data, dict):
            print(" unparseable response")
            continue

        hit = 0
        for email, prompt in batch:
            rec = data.get(email.get("email_id"))
            if not isinstance(rec, dict) or rec.get("category") not in CATEGORIES:
                continue
            try:
                conf = max(0.0, min(float(rec.get("confidence", 0.7)), 1.0))
            except (TypeError, ValueError):
                conf = 0.7
            _cache_put(_cache_key(prompt),
                       {"category": rec["category"], "confidence": conf,
                        "why": str(rec.get("why", ""))[:60],
                        "email_id": email.get("email_id")})
            hit += 1
        written += hit
        print(f" {hit}/{len(batch)} classified")

    return written


def stats() -> dict:
    return dict(_stats)