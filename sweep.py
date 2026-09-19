#!/usr/bin/env python3
"""
sweep.py — score the pipeline across freshly generated datasets.

The supplied data is exactly `generate.py --seed 42 --n 500`. The generator
ships in sdoc-hackathon-docker/data_v2/, so we can make datasets we have
never seen and check we are generalising rather than memorising.

    python sweep.py                        # seeds 101,202,303,404,505
    python sweep.py --seeds 7 13 99        # pick your own
    python sweep.py --n 300 --llm          # bigger sets, Gemini fallback on
    python sweep.py --keep                 # don't delete the generated data
    python sweep.py --md SWEEP.md          # save the report as Markdown

Read the SPREAD, not the mean. A high average with one bad seed means a
fragile rule. Consistency is the claim we want to make in the deck.
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path


_transcript: list[str] = []
_print = print


def print(*args, **kwargs):          # noqa: A001 - deliberate shadow
    _print(*args, **kwargs)
    _transcript.append(" ".join(str(a) for a in args))


def find(*names) -> Path:
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    sys.exit(f"Could not find any of {names} in {Path.cwd()}")


BUNDLE = find("sdoc-hackathon-bundle", "bundle")
DOCKER = find("sdoc-hackathon-docker", "docker")
GENERATOR = DOCKER / "data_v2" / "generate.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(DOCKER / "server"))
import scoring  # noqa: E402
from sdoc.core.pipeline import FolderSource, run, to_submission  # noqa: E402


def score_folder(folder: Path, gt_path: Path, llm=None) -> dict:
    sub = to_submission(run(FolderSource(folder), llm_classify=llm))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    return scoring.score_all(gt, sub)


def generate(seed: int, n: int, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(GENERATOR), "--seed", str(seed),
         "--n", str(n), "--out", str(out)],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        sys.exit(f"generator failed for seed {seed}:\n{r.stderr[:500]}")


def row(label: str, r: dict) -> str:
    s1, s3, e2e = r["stage1"], r["stage3"], r["end_to_end"]
    return (f"{label:<22}{r['final_score']:>8.4f}{s1['macro_f1']:>10.4f}"
            f"{s3['defect_precision']:>10.3f}{s3['defect_recall']:>9.3f}"
            f"{e2e['rate']:>9.4f}  {e2e['success']}/{e2e['total']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+",
                    default=[101, 202, 303, 404, 505])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--keep", action="store_true",
                    help="keep generated data in ./heldout/seed_<n>/")
    ap.add_argument("--csv", help="append results to this CSV")
    ap.add_argument("--md", help="save the report as Markdown")
    args = ap.parse_args()

    llm = None
    if args.llm:
        from sdoc.llm.gemini import classify_email
        llm = classify_email

    header = (f"{'dataset':<22}{'final':>8}{'macroF1':>10}"
              f"{'defP':>10}{'defR':>9}{'e2e':>9}")
    print(header)
    print("-" * len(header) + "  " + "-" * 7)

    # the supplied set, for reference
    base = score_folder(BUNDLE, DOCKER / "data_v2" / "ground_truth.json", llm)
    print(row("supplied (seed 42)", base))
    print()

    results = []
    workdir = Path("heldout") if args.keep else Path(tempfile.mkdtemp(prefix="sweep_"))
    try:
        for seed in args.seeds:
            out = workdir / f"seed_{seed}"
            if not (out / "ground_truth.json").exists():
                generate(seed, args.n, out)
            r = score_folder(out, out / "ground_truth.json", llm)
            results.append((seed, r))
            print(row(f"held-out seed {seed}", r))
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)

    finals = [r["final_score"] for _, r in results]
    print()
    print(f"held-out mean   {statistics.mean(finals):.4f}")
    print(f"held-out min    {min(finals):.4f}   max {max(finals):.4f}")
    if len(finals) > 1:
        print(f"std dev         {statistics.pstdev(finals):.4f}")
    print(f"supplied        {base['final_score']:.4f}")

    gap = statistics.mean(finals) - base["final_score"]
    print()
    if gap < -0.03:
        print(f"WARNING: held-out is {abs(gap):.3f} below the supplied set.")
        print("Something is fitted to seed 42. Find it before it costs you.")
    else:
        print(f"Generalises. Held-out is within {abs(gap):.3f} of the supplied set.")

    if args.csv:
        import csv
        from datetime import date
        new = not Path(args.csv).exists()
        with open(args.csv, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["date", "dataset", "final", "macro_f1",
                            "defect_p", "defect_r", "e2e"])
            today = date.today().isoformat()
            for label, r in [("seed42", base)] + [(f"seed{s}", x) for s, x in results]:
                w.writerow([today, label, round(r["final_score"], 4),
                            round(r["stage1"]["macro_f1"], 4),
                            round(r["stage3"]["defect_precision"], 3),
                            round(r["stage3"]["defect_recall"], 3),
                            round(r["end_to_end"]["rate"], 4)])
        print(f"appended to {args.csv}")

    if args.md:
        write_markdown(args.md, "\n".join(_transcript))


def write_markdown(path: str, body: str) -> None:
    from datetime import datetime
    doc = (f"# Seed sweep\n\n"
           f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by `sweep.py`.\n\n"
           f"Each held-out dataset is generated from a seed the pipeline has "
           f"never seen, using the organisers' own `generate.py`. A tight "
           f"spread means the rules generalise rather than memorise.\n\n"
           f"```\n{body.rstrip()}\n```\n")
    Path(path).write_text(doc, encoding="utf-8")
    _print(f"wrote {path}")


if __name__ == "__main__":
    main()