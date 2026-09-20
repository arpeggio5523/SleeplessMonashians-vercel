#!/usr/bin/env python3
r"""
verify_results.py — one command that checks the whole pipeline, including
data nobody has ever run.

    python verify_results.py                 # full check, ~3 minutes
    python verify_results.py --quick         # skip unseen-data generation
    python verify_results.py --unseen 5      # more random datasets
    python verify_results.py --llm           # include the Gemini comparison
    python verify_results.py --md docs\\VERIFY.md

Every check prints PASS or FAIL with the number it got and the number it
expected. Exits non-zero if anything failed, so it works in CI too.

The unseen-data check picks RANDOM seeds each run. It generates fresh
datasets with the organisers' own generate.py, so it is a genuine test of
whether the rules generalise rather than memorise. Pass --seed-base to make
a run reproducible.


WHAT THIS SCRIPT WRITES

  Nothing you need to clean up before committing. Specifically:

    submission.json   NOT touched - scoring happens in memory
    .cache/llm/       read only, unless --llm hits an uncached seed
    generated data    written to a system temp dir and deleted in a
                      finally block, so it goes even on Ctrl-C
    __pycache__/      created by Python, already in .gitignore
    docs/VERIFY.md    only with --md, and that one is worth committing

  Safe to run before or after `git add`.


RESETTING ANYWAY

  All of this is gitignored, so it is cosmetic:

    # PowerShell
    Remove-Item -Recurse -Force .pytest_cache, sdoc\__pycache__,
        sdoc\core\__pycache__, sdoc\llm\__pycache__, tests\__pycache__,
        heldout -ErrorAction SilentlyContinue

    # bash
    rm -rf .pytest_cache heldout $(find . -name __pycache__ -type d)

  To rebuild what the repo actually ships:

    python run_pipeline.py          # regenerates submission.json

  To confirm nothing unexpected is staged:

    git status --short


SECRETS

  No API key is stored anywhere in this repo. sdoc/llm/gemini.py reads
  GEMINI_API_KEY from the environment at call time and never writes it to
  disk. The cached files under .cache/llm/ hold only a category, a
  confidence, a one-line reason and an email id. .gitignore also blocks
  .env, *.key and service-account*.json.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- transcript
_lines: list[str] = []
_print = print


def print(*a, **k):                      # noqa: A001 - deliberate shadow
    _print(*a, **k)
    _lines.append(" ".join(str(x) for x in a))


PASS, FAIL, INFO, SKIP = "PASS", "FAIL", "    ", "SKIP"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, got: str, want: str) -> bool:
    tag = PASS if ok else FAIL
    results.append((tag, name, got))
    print(f"  [{tag}] {name:<42} {got:<22} expected {want}")
    return ok


def note(msg: str) -> None:
    print(f"         {msg}")


def head(title: str) -> None:
    print()
    print(f"  {title}")
    print("  " + "\u2500" * 76)


# ---------------------------------------------------------------- locate
def find(*names) -> Path:
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    sys.exit(f"\n  Could not find any of {names} in {Path.cwd()}\n"
             "  Extract the organisers' two zips into the project root, then\n"
             "  run this from that folder.\n")


BUNDLE = find("sdoc-hackathon-bundle", "bundle")
DOCKER = find("sdoc-hackathon-docker", "docker")
GENERATOR = DOCKER / "data_v2" / "generate.py"
GT = DOCKER / "data_v2" / "ground_truth.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(DOCKER / "server"))

try:
    from sdoc.core.ingest import poppler_path as _pp
    POPPLER_AT = _pp()
except Exception:
    POPPLER_AT = shutil.which("pdftotext")
HAS_POPPLER = POPPLER_AT is not None

# Expected scores differ by extractor. poppler reconstructs PDF columns
# properly; pdfplumber is the pure-Python fallback and loses ~0.013.
EXPECT = {
    True:  {"rules": 0.9904, "llm": 0.9995, "e2e": 1.0000, "unseen_min": 0.97},
    False: {"rules": 0.9773, "llm": 0.9864, "e2e": 0.9783, "unseen_min": 0.93},
}[HAS_POPPLER]

TOL = 0.002


def near(got: float, want: float, tol: float = TOL) -> bool:
    return abs(got - want) <= tol


# ---------------------------------------------------------------- checks
def step_environment() -> bool:
    head("1. ENVIRONMENT")
    ok = True
    v = sys.version_info
    ok &= check("python >= 3.9", v >= (3, 9),
                f"{v.major}.{v.minor}.{v.micro}", ">= 3.9")

    for mod, pkg in [("pdfplumber", "pdfplumber"), ("docx", "python-docx"),
                     ("openpyxl", "openpyxl"), ("reportlab", "reportlab")]:
        try:
            __import__(mod)
            present = True
        except ImportError:
            present = False
        ok &= check(f"{pkg} installed", present,
                    "yes" if present else "MISSING", "yes")
    if not ok:
        note("fix: pip install -r requirements.txt")

    check("poppler available", True,
          (POPPLER_AT or "no (using pdfplumber)")[-42:], "optional")
    if not HAS_POPPLER:
        note("without poppler the score is ~0.013 lower; the container installs it.")
        note("unzip poppler under your home folder and it is found automatically,")
        note("or set SDOC_POPPLER_PATH to its bin directory.")
    return ok


def step_data() -> bool:
    head("2. SUPPLIED DATA")
    ok = True
    n_inbox = len(list((BUNDLE / "inbox").glob("email_*.json")))
    n_att = len(list((BUNDLE / "attachments").glob("*")))
    ok &= check("inbox records", n_inbox == 520, str(n_inbox), "520")
    ok &= check("attachments", n_att == 250, str(n_att), "250")

    if GT.exists():
        import hashlib
        digest = hashlib.sha256(GT.read_bytes()).hexdigest()
        want = "d2d84f55cd68e9e0e7a62f07616d49968f44be2132c7b6b69a77213adfc0babe"
        good = digest == want
        ok &= check("benchmark checksum", good, digest[:16], want[:16])
        if not good:
            note("data_v2 was overwritten, probably by generate.py without --out.")
            note("restore:  python " + str(GENERATOR) +
                 " --seed 42 --n 500 --out " + str(DOCKER / "data_v2"))
    else:
        ok &= check("ground_truth.json", False, "missing", "present")
    return ok


def _score(folder: Path, gt_path: Path, llm=None):
    """Returns (scoreboard, submission, ground_truth)."""
    from sdoc.core.pipeline import FolderSource, run, to_submission
    import scoring
    src = FolderSource(folder)

    # Batch the low-confidence cases into a couple of requests before the
    # run, exactly as run_pipeline.py does. Without this the per-email hook
    # fires once per email — ~25 requests per dataset instead of 2, which
    # exhausts a free-tier daily quota in one go.
    if llm is not None:
        from sdoc.core.classify import classify as rule_classify
        from sdoc.core.contract import CONFIDENCE_THRESHOLD
        from sdoc.llm.gemini import prefetch_classifications
        unsure = [e for e in src.emails()
                  if rule_classify(e).confidence < CONFIDENCE_THRESHOLD]
        if unsure:
            prefetch_classifications(unsure)

    sub = to_submission(run(src, llm_classify=llm))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    return scoring.score_all(gt, sub), sub, gt


def step_pipeline() -> tuple[bool, dict]:
    head("3. PIPELINE ON THE SUPPLIED DATA")
    t0 = time.time()
    r, sub, gt = _score(BUNDLE, GT)
    ok = True
    ok &= check("final score", near(r["final_score"], EXPECT["rules"]),
                f"{r['final_score']:.4f}", f"{EXPECT['rules']:.4f}")
    ok &= check("end-to-end", near(r["end_to_end"]["rate"], EXPECT["e2e"]),
                f"{r['end_to_end']['rate']:.4f} "
                f"({r['end_to_end']['success']}/{r['end_to_end']['total']})",
                f"{EXPECT['e2e']:.4f}")
    ok &= check("defect precision", near(r["stage3"]["defect_precision"], 1.0),
                f"{r['stage3']['defect_precision']:.3f}", "1.000 (no false alarms)")
    ok &= check("classification accuracy", r["stage1"]["accuracy"] > 0.98,
                f"{r['stage1']['accuracy']:.4f}", "> 0.98")
    note(f"{time.time() - t0:.1f}s")
    if not ok and r["final_score"] < 0.7:
        note("a score near 0.58 means attachments were read with the OS default")
        note("encoding instead of UTF-8 — see sdoc/core/ingest.decode()")
    return ok, r, sub


def step_tests() -> bool:
    head("4. UNIT TESTS")
    try:
        import pytest  # noqa: F401
    except ImportError:
        results.append((SKIP, "pytest", "not installed"))
        print(f"  [{SKIP}] {'pytest':<42} {'not installed':<22} "
              "expected 46 passed")
        note("pip install pytest   (not counted as a failure)")
        return True

    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"],
                       capture_output=True, text=True)
    out = (p.stdout + p.stderr).strip().split("\n")[-1][:60]
    ok = p.returncode == 0
    check("pytest", ok, out, "46 passed")
    if not ok:
        note("run 'python -m pytest -q' for detail")
    return ok


def step_llm(rules: dict, rules_sub: dict) -> bool:
    """Section 5 — the same comparison compare.py performs, inline."""
    head("5. RULES vs RULES + GEMINI (the comparison compare.py runs)")
    try:
        from sdoc.llm.gemini import classify_email, stats
    except Exception as e:
        check("import sdoc.llm.gemini", False, str(e)[:30], "importable")
        return False

    llm, llm_sub, gt = _score(BUNDLE, GT, llm=classify_email)
    s = stats()

    print(f"         {'':24}{'rules':>10}{'+ Gemini':>11}{'change':>10}")
    for name, a, b in [
        ("final score", rules["final_score"], llm["final_score"]),
        ("stage1 macro-F1", rules["stage1"]["macro_f1"], llm["stage1"]["macro_f1"]),
        ("stage1 accuracy", rules["stage1"]["accuracy"], llm["stage1"]["accuracy"]),
        ("stage3 defect-F1", rules["stage3"]["defect_f1"], llm["stage3"]["defect_f1"]),
        ("end-to-end", rules["end_to_end"]["rate"], llm["end_to_end"]["rate"]),
    ]:
        d = b - a
        ds = "\u2014".rjust(10) if abs(d) < 1e-9 else f"{d:+10.4f}"
        print(f"         {name:<24}{a:>10.4f}{b:>11.4f}{ds}")

    # which emails the model actually changed
    fixed = broke = 0
    for eid, t in gt.items():
        a, b = rules_sub[eid]["category"], llm_sub[eid]["category"]
        if a == b:
            continue
        if b == t["category"]:
            fixed += 1
        elif a == t["category"]:
            broke += 1
    print()

    ok = True
    ok &= check("final score", near(llm["final_score"], EXPECT["llm"]),
                f"{llm['final_score']:.4f}", f"{EXPECT['llm']:.4f}")
    ok &= check("classification macro-F1", llm["stage1"]["macro_f1"] > 0.99,
                f"{llm['stage1']['macro_f1']:.4f}", "> 0.99")
    ok &= check("emails the model fixed", fixed >= 7, str(fixed), ">= 7")
    ok &= check("emails the model broke", broke == 0, str(broke), "0")
    cached = s["cache_hits"] > 0 and s["calls"] == 0
    ok &= check("served from cache, no API calls", cached,
                f"hits {s['cache_hits']}, calls {s['calls']}", "calls 0")
    if not cached:
        note("the committed .cache/llm/ should make this run offline")
    return ok


def step_unseen(n: int, size: int, base: int | None, use_llm: bool) -> bool:
    head(f"6. UNSEEN DATA \u2014 {n} dataset(s) generated from random seeds")
    if not GENERATOR.exists():
        check("generator present", False, "missing", str(GENERATOR))
        return False

    rng = random.Random(base)
    seeds = rng.sample(range(10_000, 999_999), n)
    note(f"seeds {seeds}  (random this run; --seed-base makes it repeatable)")

    llm = None
    if use_llm:
        from sdoc.llm.gemini import classify_email
        llm = classify_email

    work = Path(tempfile.mkdtemp(prefix="verify_"))
    finals, ok = [], True
    try:
        for seed in seeds:
            out = work / f"seed_{seed}"
            out.mkdir(parents=True, exist_ok=True)
            p = subprocess.run(
                [sys.executable, str(GENERATOR), "--seed", str(seed),
                 "--n", str(size), "--out", str(out)],
                capture_output=True, text=True, timeout=600)
            if p.returncode != 0:
                check(f"generate seed {seed}", False,
                      p.stderr.strip()[-60:], "success")
                note("missing reportlab? pip install reportlab")
                ok = False
                continue

            r, _, _ = _score(out, out / "ground_truth.json", llm)
            finals.append(r["final_score"])
            good = (r["final_score"] >= EXPECT["unseen_min"]
                    and near(r["stage3"]["defect_precision"], 1.0))
            ok &= check(f"seed {seed}", good,
                        f"{r['final_score']:.4f}  P {r['stage3']['defect_precision']:.3f}"
                        f"  e2e {r['end_to_end']['rate']:.3f}",
                        f">= {EXPECT['unseen_min']:.2f}, P 1.000")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if len(finals) > 1:
        mean = statistics.mean(finals)
        sd = statistics.pstdev(finals)
        print()
        ok &= check("held-out mean", mean >= EXPECT["unseen_min"],
                    f"{mean:.4f}", f">= {EXPECT['unseen_min']:.2f}")
        ok &= check("consistency (std dev)", sd < 0.02, f"{sd:.4f}", "< 0.02")
        note("a tight spread on data we have never seen is the point of this step")
    return ok


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="skip the unseen-data generation (steps 1-5 only)")
    ap.add_argument("--unseen", type=int, default=3,
                    help="how many random datasets to generate (default 3)")
    ap.add_argument("--n", type=int, default=500,
                    help="emails per generated dataset (default 500)")
    ap.add_argument("--seed-base", type=int, default=None,
                    help="make the random seed choice reproducible")
    ap.add_argument("--llm", action="store_true",
                    help="also run the Gemini fallback on the unseen data "
                         "(needs GEMINI_API_KEY for uncached seeds)")
    ap.add_argument("--md", help="save this report as Markdown")
    args = ap.parse_args()

    print()
    print("  " + "=" * 76)
    print("  SDOC \u2014 VERIFICATION")
    print("  " + "=" * 76)
    print(f"  {datetime.now():%Y-%m-%d %H:%M}   "
          f"extractor: {'poppler' if HAS_POPPLER else 'pdfplumber'}")

    ok = True
    ok &= step_environment()
    ok &= step_data()
    p_ok, rules, rules_sub = step_pipeline()
    ok &= p_ok
    ok &= step_tests()
    ok &= step_llm(rules, rules_sub)
    if args.quick:
        head("6. UNSEEN DATA")
        print(f"  [{SKIP}] skipped (--quick)")
    else:
        ok &= step_unseen(args.unseen, args.n, args.seed_base, args.llm)

    n_pass = sum(1 for t, _, _ in results if t == PASS)
    n_fail = sum(1 for t, _, _ in results if t == FAIL)
    print()
    print("  " + "=" * 76)
    if ok and not n_fail:
        print(f"  ALL {n_pass} CHECKS PASSED")
        print("  " + "=" * 76)
        print("  The pipeline reproduces its published numbers, and holds up on")
        print("  data generated from seeds it had never been run against.")
    else:
        print(f"  {n_fail} CHECK(S) FAILED   ({n_pass} passed)")
        print("  " + "=" * 76)
        for t, name, got in results:
            if t == FAIL:
                print(f"    * {name}  \u2014 got {got}")
    print()

    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(
            f"# Verification report\n\n"
            f"{datetime.now():%Y-%m-%d %H:%M} \u00b7 "
            f"extractor: {'poppler' if HAS_POPPLER else 'pdfplumber'}\n\n"
            "Generated by `python verify_results.py`. The unseen-data section "
            "uses randomly chosen seeds, so each run tests datasets the "
            "pipeline has never been scored against.\n\n"
            "```\n" + "\n".join(_lines).rstrip() + "\n```\n",
            encoding="utf-8")
        _print(f"  wrote {args.md}\n")

    sys.exit(0 if ok and not n_fail else 1)


if __name__ == "__main__":
    main()