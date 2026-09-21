"""
ocr.py - read scanned, image-only PDFs, for human review only.

Owner: I (intelligence).

WHAT THIS IS FOR
    Three emails in the supplied data carry genuine scans with no text layer.
    Without OCR they escalate as `unreadable` and a reviewer types every value
    from scratch. With OCR the reviewer gets a pre-filled form to confirm.

WHAT THIS IS NOT FOR
    Deciding anything. OCR misreads are plausible-looking: on email_512
    tesseract returned "128.544" where the page says "128,544" - a thousand-
    fold error that parses cleanly and would compare as a discrepancy. So:

      - extract.py caps every OCR-derived field at confidence 0.50, below the
        0.60 threshold, so nothing from OCR is ever compared as fact
      - pipeline.py keeps these emails as NEEDS_REVIEW / unreadable, so the
        reason code does not change depending on whether tesseract happens
        to be installed on the machine

    It cannot change the score: those rows are graded NEEDS_REVIEW, which
    score_stage3 skips and end_to_end does not count.

ORDER
    1. rasterise with poppler's pdftoppm (found beside the validated pdftotext)
    2. tesseract - fast, local, free
    3. Gemini vision, only if tesseract output is poor, only in live mode,
       cached by image hash so a re-run makes no calls

    Every failure returns readable=False with a reason. Nothing raises, so a
    missing binary can never stop the other 519 emails.

ENVIRONMENT
    SDOC_TESSERACT_PATH   tesseract binary, if not in a standard place
    SDOC_OCR              "off" disables OCR entirely
    SDOC_LLM_MODE         vision is only attempted when this is "live"
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

OCR_TIMEOUT = 60          # seconds per subprocess; tesseract can hang on bad input
DPI = 200


# --------------------------------------------------------------------------
# binaries - found the same way as pdftotext, never trusted blindly from PATH
# --------------------------------------------------------------------------

def _pdftoppm() -> Optional[str]:
    """
    pdftoppm lives beside pdftotext in every poppler distribution. Reuse the
    pdftotext that ingest.py already validated as genuine poppler, rather
    than taking whatever 'pdftoppm' is first on PATH - MiKTeX ships one too.
    """
    from .ingest import _find_pdftotext
    pdftotext = _find_pdftotext()
    if not pdftotext:
        return None
    exe = "pdftoppm.exe" if os.name == "nt" else "pdftoppm"
    beside = Path(pdftotext).parent / exe
    return str(beside) if beside.is_file() else None


def _tesseract() -> Optional[str]:
    explicit = os.environ.get("SDOC_TESSERACT_PATH")
    if explicit and Path(explicit).is_file():
        return explicit
    for cand in (shutil.which("tesseract"),
                 r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                 r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                 "/usr/bin/tesseract", "/usr/local/bin/tesseract",
                 "/opt/homebrew/bin/tesseract"):
        if cand and Path(cand).is_file():
            return cand
    return None


def ocr_available() -> dict:
    """For diagnostics: which OCR tools this machine has."""
    return {"pdftoppm": _pdftoppm(), "tesseract": _tesseract()}


# --------------------------------------------------------------------------
# quality gate
# --------------------------------------------------------------------------

def _is_poor(text: str) -> bool:
    cleaned = text.strip()
    if len(cleaned) < 40:
        return True
    words = [w for w in cleaned.split() if any(c.isalnum() for c in w)]
    if len(words) < 10:
        return True
    return sum(c.isalnum() for c in cleaned) / len(cleaned) < 0.60


# --------------------------------------------------------------------------
# vision fallback - reuses the shared Gemini client, model, cache and limits
# --------------------------------------------------------------------------

VISION_PROMPT = (
    "Transcribe all text from this scanned document page exactly as printed. "
    "Preserve layout, numbers, decimal marks, thousands separators and "
    "punctuation verbatim. Do not summarise, correct or interpret."
)


def _vision_config(gemini):
    """
    Plain text, deterministic, minimal reasoning.

    Deliberately NOT gemini._config(): that forces JSON output, which is right
    for classification and wrong for a transcription - the page text would
    come back wrapped in a JSON string and the label matcher would be reading
    escaped quotes and newlines.
    """
    from google.genai import types
    thinking = (types.ThinkingConfig(thinking_budget=0)
                if "2.5" in gemini.MODEL or "2.0" in gemini.MODEL
                else types.ThinkingConfig(thinking_level="minimal"))
    try:
        return types.GenerateContentConfig(temperature=0.0,
                                           max_output_tokens=4096,
                                           thinking_config=thinking)
    except Exception:
        return types.GenerateContentConfig(temperature=0.0,
                                           max_output_tokens=4096)


def _vision(image: Path, warnings: list[str]) -> str:
    """One page. Cached by image hash, so re-runs cost nothing."""
    try:
        from ..llm import gemini
    except Exception as exc:
        warnings.append(f"vision unavailable: {exc}")
        return ""

    img = image.read_bytes()
    key = "vision-" + hashlib.sha256(img).hexdigest()[:24]
    hit = gemini._cache_get(key)
    if hit and hit.get("text"):
        return hit["text"]

    if gemini.MODE != "live":
        warnings.append(f"vision skipped (SDOC_LLM_MODE={gemini.MODE})")
        return ""

    try:
        from google.genai import types
        gemini._throttle()
        resp = gemini._get_client().models.generate_content(
            model=gemini.MODEL,
            contents=[types.Part.from_bytes(data=img, mime_type="image/png"),
                      VISION_PROMPT],
            config=_vision_config(gemini),
        )
        text = (getattr(resp, "text", "") or "").strip()
    except Exception as exc:
        warnings.append(f"vision failed: {str(exc)[:120]}")
        return ""

    if text:
        gemini._cache_put(key, {"text": text, "source": "vision"})
    return text


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def process_scanned_pdf(raw: bytes, warnings: list[str]) -> tuple[str, bool, list[str]]:
    """
    Returns (text, readable, warnings). Never raises.

    readable=True means *some* text was recovered, not that it is correct.
    Callers must treat it as a suggestion - see the module docstring.
    """
    if os.environ.get("SDOC_OCR", "").lower() == "off":
        warnings.append("OCR disabled (SDOC_OCR=off)")
        return "", False, warnings

    pdftoppm = _pdftoppm()
    if not pdftoppm:
        warnings.append("OCR unavailable: poppler's pdftoppm not found")
        return "", False, warnings

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        pdf = tmp_dir / "in.pdf"
        pdf.write_bytes(raw)

        try:
            subprocess.run([pdftoppm, "-r", str(DPI), "-png", str(pdf),
                            str(tmp_dir / "page")],
                           capture_output=True, check=True, timeout=OCR_TIMEOUT)
        except subprocess.CalledProcessError:
            warnings.append("not a valid PDF - cannot rasterise")
            return "", False, warnings
        except Exception as exc:
            warnings.append(f"rasterise failed: {exc}")
            return "", False, warnings

        pages = sorted(tmp_dir.glob("page-*.png"))
        if not pages:
            warnings.append("no pages rasterised")
            return "", False, warnings

        tesseract = _tesseract()
        if not tesseract:
            warnings.append("tesseract not found - trying vision only")

        out: list[str] = []
        used_vision = False
        for page in pages:
            text = ""
            if tesseract:
                try:
                    r = subprocess.run([tesseract, str(page), "stdout"],
                                       capture_output=True, text=True,
                                       check=True, timeout=OCR_TIMEOUT)
                    text = r.stdout.strip()
                except Exception as exc:
                    warnings.append(f"tesseract failed on {page.name}: {exc}")

            # per page: a good tesseract page is kept, only a poor one
            # is re-read by the model
            if _is_poor(text):
                vision = _vision(page, warnings)
                if vision:
                    text, used_vision = vision, True
            out.append(text)

        final = "\n\n".join(t for t in out if t.strip())
        if not final.strip():
            warnings.append("OCR recovered no text")
            return "", False, warnings

        warnings.append("text recovered by OCR" + (" and vision" if used_vision else "")
                        + " - for review only, not compared")
        return final, True, warnings
