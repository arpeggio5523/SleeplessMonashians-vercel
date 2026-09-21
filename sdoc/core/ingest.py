"""
ingest.py — attachment bytes -> plain text.

Owner: I (intelligence). Swap any reader for a cloud service (Document AI,
Textract) without touching anything else: the contract is
(path, bytes) -> IngestResult.

Formats: .txt .pdf .docx .xlsx. Returns readable=False rather than raising,
so the pipeline can escalate instead of crashing.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Minimum characters before we believe an extraction succeeded. Image-only
# PDFs typically return a handful of stray glyphs, not nothing.
MIN_USEFUL_CHARS = 40


# --------------------------------------------------------------------------
# poppler discovery
# --------------------------------------------------------------------------
#
# pdftotext is a system binary, not a Python package, so pip cannot supply it.
# The container installs it via apt (poppler-utils) and it is simply on PATH.
# On a developer laptop it is usually unzipped somewhere and forgotten, and a
# session-scoped PATH edit is lost the moment the terminal closes - which
# quietly costs ~0.013 of the score and confuses everyone.
#
# So look on PATH first, then in the handful of places it actually gets
# installed. Set SDOC_POPPLER_PATH to point at the bin directory explicitly.

_POPPLER_CACHED: Optional[str] = None
_POPPLER_INFO: dict = {}
_POPPLER_LOOKED = False


def _is_poppler(exe: str) -> Optional[str]:
    """
    Return the version string if `exe` is poppler's pdftotext, else None.

    Several programs ship a binary called pdftotext. MiKTeX and xpdf in
    particular put one on PATH that lays out PDF columns differently. On this
    dataset that difference is not cosmetic: it produced false-alarm
    discrepancies (defect precision 0.958 instead of 1.000). So only accept a
    binary that identifies itself as poppler.
    """
    try:
        r = subprocess.run([exe, "-v"], capture_output=True, text=True,
                           timeout=10)
    except Exception:
        return None
    out = (r.stdout or "") + (r.stderr or "")
    if "poppler" not in out.lower():
        return None
    first = out.strip().splitlines()[0] if out.strip() else ""
    return first.replace("pdftotext version", "").strip() or "unknown"


def _find_pdftotext() -> Optional[str]:
    """
    Full path to POPPLER's pdftotext, or None to use pdfplumber instead.

    Order:
      1. SDOC_POPPLER_PATH, if set - an explicit choice always wins
      2. the places poppler is normally unpacked or installed
      3. whatever is on PATH, last, because PATH is where impostors live

    Every candidate is checked with `pdftotext -v`; anything that is not
    poppler is skipped rather than used.
    """
    global _POPPLER_CACHED, _POPPLER_LOOKED, _POPPLER_INFO
    if _POPPLER_LOOKED:
        return _POPPLER_CACHED
    _POPPLER_LOOKED = True

    exe = "pdftotext.exe" if os.name == "nt" else "pdftotext"
    skipped: list = []

    def candidates():
        explicit = os.environ.get("SDOC_POPPLER_PATH")
        if explicit:
            e = Path(explicit)
            yield e if e.is_file() else e / exe
        home = Path.home()
        for root in (home / "poppler", Path("C:/poppler"),
                     Path("C:/Program Files/poppler"),
                     Path("/usr/bin"), Path("/usr/local/bin"),
                     Path("/opt/homebrew/bin")):
            try:
                if not root.exists():
                    continue
                direct = root / exe
                if direct.is_file():
                    yield direct
                for hit in root.rglob(exe):
                    yield hit
            except (OSError, PermissionError):
                continue
        on_path = shutil.which("pdftotext")
        if on_path:
            yield Path(on_path)

    seen = set()
    for cand in candidates():
        key = str(cand).lower()
        if key in seen or not cand.is_file():
            continue
        seen.add(key)
        version = _is_poppler(str(cand))
        if version:
            _POPPLER_CACHED = str(cand)
            _POPPLER_INFO = {"path": str(cand), "version": version,
                             "skipped": skipped}
            return _POPPLER_CACHED
        skipped.append(str(cand))

    _POPPLER_INFO = {"path": None, "version": None, "skipped": skipped}
    return None


@dataclass
class IngestResult:
    text: str = ""
    method: str = "text"          # text | pdf | docx | xlsx | ocr
    readable: bool = True
    warnings: list[str] | None = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# --------------------------------------------------------------------------
# decoding
# --------------------------------------------------------------------------

def decode(raw: bytes) -> str:
    """
    Decode attachment bytes. ALWAYS explicit — never rely on the platform
    default, which is cp1252 on Windows and mangles the 51 files carrying
    the bilingual label 'Gross Weight毛重(KGS)'.
    """
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def strip_non_ascii(line: str) -> str:
    """
    Remove non-ASCII so a CJK label and any mojibake of it reduce to the
    same ASCII stem. 'Gross Weight毛重(KGS):' -> 'Gross Weight(KGS):'
    """
    line = unicodedata.normalize("NFKC", line)
    return "".join(ch if ord(ch) < 128 else "" for ch in line).strip()


# --------------------------------------------------------------------------
# per-format readers
# --------------------------------------------------------------------------

def _read_pdf(raw: bytes, path: str) -> IngestResult:
    warnings: list[str] = []

    # poppler is fastest and preserves column layout best, when present
    pdftotext = _find_pdftotext()
    if pdftotext:
        try:
            p = subprocess.run([pdftotext, "-layout", "-", "-"],
                               input=raw, capture_output=True, timeout=30)
            text = p.stdout.decode("utf-8", "replace")
            if len(text.strip()) > MIN_USEFUL_CHARS:
                return IngestResult(text, "pdf", True, warnings)
        except Exception as e:
            warnings.append(f"pdftotext failed: {e}")

    # pure-python fallback — this is the Windows path
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            text = "\n".join((pg.extract_text(layout=True) or "") for pg in pdf.pages)
        if len(text.strip()) > MIN_USEFUL_CHARS:
            return IngestResult(text, "pdf", True, warnings)
        warnings.append("no text layer — likely a scanned/image-only PDF")
    except ImportError:
        warnings.append("pdfplumber not installed")
    except Exception as e:
        warnings.append(f"pdfplumber failed: {e}")

    # Last resort: the page is an image. OCR it for the human reviewer.
    # Anything recovered is capped below the trust threshold in extract.py
    # and never compared - see sdoc/core/ocr.py.
    from .ocr import process_scanned_pdf
    text, readable, warnings = process_scanned_pdf(raw, warnings)
    return IngestResult(text, "ocr", readable, warnings)


def _read_docx(raw: bytes, path: str) -> IngestResult:
    try:
        import docx
    except ImportError:
        return IngestResult("", "docx", False, ["python-docx not installed"])
    try:
        d = docx.Document(io.BytesIO(raw))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.replace("\n", " | ") for c in row.cells]
                parts.append(": ".join(cells))
        text = "\n".join(parts)
        return IngestResult(text, "docx", len(text.strip()) > MIN_USEFUL_CHARS)
    except Exception as e:
        return IngestResult("", "docx", False, [f"docx read failed: {e}"])


def _read_xlsx(raw: bytes, path: str) -> IngestResult:
    try:
        import openpyxl
    except ImportError:
        return IngestResult("", "xlsx", False, ["openpyxl not installed"])
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        parts = []
        for ws in wb:
            for row in ws.iter_rows(values_only=True):
                vals = [str(c) for c in row if c is not None]
                if vals:
                    parts.append(": ".join(vals))
        text = "\n".join(parts)
        return IngestResult(text, "xlsx", len(text.strip()) > MIN_USEFUL_CHARS)
    except Exception as e:
        return IngestResult("", "xlsx", False, [f"xlsx read failed: {e}"])


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

READERS = {".pdf": _read_pdf, ".docx": _read_docx, ".xlsx": _read_xlsx}


def poppler_path() -> Optional[str]:
    """Where poppler's pdftotext was found, for diagnostics. None = pdfplumber."""
    return _find_pdftotext()


def poppler_info() -> dict:
    """{'path', 'version', 'skipped'} - skipped lists non-poppler pdftotext
    binaries that were found and deliberately ignored."""
    _find_pdftotext()
    return dict(_POPPLER_INFO)


def ingest(path: str, raw: Optional[bytes]) -> IngestResult:
    """
    path : the attachment path, used only for its extension
    raw  : the file bytes, or None if the attachment could not be fetched
    """
    if raw is None:
        return IngestResult("", "text", False, ["attachment not found"])
    if not raw:
        return IngestResult("", "text", False, ["attachment is empty"])

    ext = Path(path).suffix.lower()
    if ext in READERS:
        return READERS[ext](raw, path)

    text = decode(raw)
    return IngestResult(text, "text", len(text.strip()) > MIN_USEFUL_CHARS)