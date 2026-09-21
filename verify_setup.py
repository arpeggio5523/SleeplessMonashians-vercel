#!/usr/bin/env python3
"""
verify_setup.py — run this BEFORE anything else.

Checks that the data is intact and that this machine can read every
attachment format. Every team member should run it and get the same
result, so a scoring gap between laptops never surprises you later.

    python verify_setup.py
"""
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

PASS, FAIL, WARN = "[ OK ]", "[FAIL]", "[WARN]"
problems, warnings = [], []


def ok(msg):
    print(f"{PASS} {msg}")


def bad(msg, fix):
    print(f"{FAIL} {msg}")
    problems.append((msg, fix))


def warn(msg, fix):
    print(f"{WARN} {msg}")
    warnings.append((msg, fix))


def find(*names):
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    return None


print("=" * 66)
print("  SDOC HACKATHON — SETUP VERIFICATION")
print("=" * 66)

# ---------------------------------------------------------------- 1. Python
print("\n1. Python")
v = sys.version_info
if v >= (3, 9):
    ok(f"Python {v.major}.{v.minor}.{v.micro}")
else:
    bad(f"Python {v.major}.{v.minor} is too old",
        "Install Python 3.9 or newer from python.org")

# ---------------------------------------------------------------- 2. Folders
print("\n2. Folder layout")
BUNDLE = find("sdoc-hackathon-bundle", "bundle")
DOCKER = find("sdoc-hackathon-docker", "docker")

if BUNDLE:
    ok(f"bundle folder: {BUNDLE}")
else:
    bad("Cannot find the participant bundle folder",
        "Unzip sdoc-hackathon-bundle.zip next to this script")

if DOCKER:
    ok(f"docker folder: {DOCKER}")
else:
    bad("Cannot find the docker folder",
        "Unzip sdoc-hackathon-docker.zip next to this script")

if not (BUNDLE and DOCKER):
    print("\nStopping — fix the folders above and re-run.")
    sys.exit(1)

# ---------------------------------------------------------------- 3. Data
print("\n3. Dataset integrity")
inbox_files = sorted((BUNDLE / "inbox").glob("email_*.json"))
att_files = sorted((BUNDLE / "attachments").glob("*"))

if len(inbox_files) == 520:
    ok("520 inbox records")
else:
    bad(f"{len(inbox_files)} inbox records (expected 520)",
        "Re-extract the bundle zip; it may be truncated")

if len(att_files) == 250:
    ok("250 attachments")
else:
    bad(f"{len(att_files)} attachments (expected 250)",
        "Re-extract the bundle zip")

ext_counts = {}
for p in att_files:
    ext_counts[p.suffix.lower()] = ext_counts.get(p.suffix.lower(), 0) + 1
ok("formats: " + ", ".join(f"{k} {v}" for k, v in sorted(ext_counts.items())))

# The supplied dataset is exactly `generate.py --seed 42 --n 500`.
# generate.py defaults --out to data_v2 itself, so running it without --out
# silently overwrites the benchmark. This checksum catches that immediately.
GT_SHA256 = "d2d84f55cd68e9e0e7a62f07616d49968f44be2132c7b6b69a77213adfc0babe"

gt_path = DOCKER / "data_v2" / "ground_truth.json"
if gt_path.exists():
    raw = gt_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    gt = json.loads(raw.decode("utf-8"))
    if digest == GT_SHA256:
        n_mm = sum(1 for r in gt.values() if r.get("status") == "MISMATCH")
        ok(f"ground truth intact: 520 records, {n_mm} MISMATCH (sha256 matches)")
    else:
        bad("ground truth does NOT match the supplied benchmark",
            "data_v2 was overwritten, probably by generate.py without --out.\n"
            "       Restore with:\n"
            "         pip install reportlab\n"
            "         python " + str(DOCKER / "data_v2" / "generate.py") +
            " --seed 42 --n 500 --out " + str(DOCKER / "data_v2") + "\n"
            "       Then re-run this script. NEVER run generate.py without --out.")
else:
    bad("ground_truth.json not found", f"Expected at {gt_path}")

# ---------------------------------------------------------------- 4. Scorer
print("\n4. Official scorer")
sys.path.insert(0, str(DOCKER / "server"))
try:
    import scoring
    w = scoring.DEFAULT_WEIGHTS
    ok(f"scoring.py imports — weights {w}")
except Exception as e:
    bad(f"cannot import scoring.py ({e})",
        f"Check {DOCKER / 'server' / 'scoring.py'} exists")

# ---------------------------------------------------------------- 5. Deps
print("\n5. Document libraries")
for mod, pkg, why in [("pdfplumber", "pdfplumber", "PDF attachments (28 files)"),
                      ("docx", "python-docx", "DOCX attachments (8 files)"),
                      ("openpyxl", "openpyxl", "XLSX attachments (22 files)")]:
    try:
        importlib.import_module(mod)
        ok(f"{pkg} — {why}")
    except ImportError:
        bad(f"{pkg} missing — needed for {why}",
            f"pip install {pkg}")

try:
    from sdoc.core.ingest import poppler_info
    _info = poppler_info()
except Exception:
    _info = {"path": shutil.which("pdftotext"), "version": None, "skipped": []}
_pp = _info.get("path")
for _bad in _info.get("skipped") or []:
    warn(f"ignored a non-poppler pdftotext: {_bad}",
         "MiKTeX and xpdf ship a binary of the same name. Its column layout\n"
         "       differs and produced false alarms on this data, so it is skipped.")
if _pp:
    ok(f"poppler {_info.get('version') or ''} found — {_pp}")
else:
    warn("poppler not found — using pdfplumber instead",
         "Optional, worth ~0.013. The container installs poppler-utils.\n"
         "       Unzip poppler anywhere under your home folder and it is found\n"
         "       automatically, or set SDOC_POPPLER_PATH to its bin directory.")

# ---------------------------------------------------------------- 6. Encoding
print("\n6. Encoding (the Windows trap)")
cjk = []
for p in (BUNDLE / "attachments").glob("*.txt"):
    if b"\xe6\xaf\x9b" in p.read_bytes():      # UTF-8 bytes for 毛
        cjk.append(p)
if cjk:
    ok(f"{len(cjk)} text files contain a bilingual label")
    sample = cjk[0]
    good = sample.read_bytes().decode("utf-8")
    if "Gross Weight毛重(KGS)" in good:
        ok("explicit UTF-8 decode reads them correctly")
    else:
        warn("bilingual label not found where expected", "Inspect " + str(sample))
    try:
        default = sample.read_text()           # no encoding= : uses OS default
        if "毛重" not in default:
            warn("your OS default encoding MANGLES these files",
                 "Always pass encoding='utf-8' when reading attachments. "
                 "baseline.py already does.")
        else:
            ok("your OS default encoding is UTF-8 too")
    except UnicodeDecodeError:
        warn("your OS default encoding cannot decode these files",
             "Always pass encoding='utf-8'. baseline.py already does.")
else:
    warn("no bilingual labels found", "Unexpected — check the bundle extracted fully")

# ---------------------------------------------------------------- 7. Extraction
print("\n7. Attachment extraction smoke test")


def try_pdf(p):
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(p), "-"],
                           capture_output=True, timeout=30)
        t = r.stdout.decode("utf-8", "replace")
        if len(t.strip()) > 40:
            return t
    import pdfplumber
    with pdfplumber.open(str(p)) as pdf:
        return "\n".join((pg.extract_text(layout=True) or "") for pg in pdf.pages)


checks = [
    (".txt", lambda p: p.read_bytes().decode("utf-8"), "shipper"),
    (".pdf", try_pdf, "shipper"),
    (".docx", lambda p: "\n".join(c.text for t in __import__("docx").Document(str(p)).tables
                                  for r in t.rows for c in r.cells), "shipper"),
    (".xlsx", lambda p: "\n".join(str(c) for ws in __import__("openpyxl")
                                  .load_workbook(str(p), data_only=True)
                                  for row in ws.iter_rows(values_only=True)
                                  for c in row if c is not None), "shipper"),
]
for ext, reader, needle in checks:
    files = [p for p in att_files if p.suffix.lower() == ext and p.stat().st_size > 0]
    if not files:
        warn(f"no {ext} files to test", "")
        continue
    got = 0
    for p in files[:6]:
        try:
            if needle.lower() in (reader(p) or "").lower():
                got += 1
        except Exception:
            pass
    if got:
        ok(f"{ext}: read {got}/{min(6, len(files))} sample files")
    else:
        bad(f"{ext}: could not read any sample file",
            f"Install the library for {ext} and re-run")

# ---------------------------------------------------------------- Summary
print("\n" + "=" * 66)
if problems:
    print(f"  {len(problems)} PROBLEM(S) — fix these before running run_pipeline.py")
    print("=" * 66)
    for m, f in problems:
        print(f"\n  * {m}\n    -> {f}")
    sys.exit(1)

print("  ALL CHECKS PASSED — you are ready to run run_pipeline.py")
print("=" * 66)
if warnings:
    print(f"\n  {len(warnings)} note(s), none blocking:")
    for m, f in warnings:
        print(f"    * {m}")
        if f:
            print(f"      {f}")
sys.exit(0)