#!/usr/bin/env python3
"""
compare.py — rules-only vs rules+LLM, side by side, with headroom analysis.

    python compare.py                         # supplied dataset only
    python compare.py --seeds 101 202 303     # plus unseen data
    python compare.py --csv compare.csv       # log it for the deck
    python compare.py --md RESULTS.md         # save the whole report

Scored metrics (from the organisers' scoring.py):

    final = 0.30 x stage1_macro_f1
          + 0.20 x stage3_defect_f1
          + 0.50 x end_to_end_rate

Everything else printed here is diagnostic: it explains the three scored
numbers but does not itself contribute to the final score.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

W = {"stage1": 0.30, "stage3": 0.20, "end_to_end": 0.50}
BAR = "\u2500"

# Everything print()ed is also collected here, so the same report can be
# written to a Markdown file for the repo and the deck.
_transcript: list[str] = []
_print = print


def print(*args, **kwargs):          # noqa: A001 - deliberate shadow
    _print(*args, **kwargs)
    _transcript.append(" ".join(str(a) for a in args))


def write_markdown(path: str, results: list) -> None:
    """Save the console report as Markdown: prose header, report in a code
    block (the alignment matters), then a clean table for the deck."""
    from datetime import datetime

    body = "\n".join(_transcript).rstrip()
    rows = []
    for name, r, l in results:
        d = l["final_score"] - r["final_score"]
        rows.append(
            f"| {name} | {r['final_score']:.4f} | {l['final_score']:.4f} | "
            f"{d:+.4f} | {l['stage1']['macro_f1']:.4f} | "
            f"{l['stage3']['defect_f1']:.4f} | {l['end_to_end']['rate']:.4f} |")

    held = [l for n, _, l in results if "held-out" in n]
    gen = ""
    if held:
        vals = [x["final_score"] for x in held]
        mean = sum(vals) / len(vals)
        gen = (f"\nHeld-out mean **{mean:.4f}** across {len(vals)} datasets "
               f"generated with seeds the pipeline had never seen "
               f"(range {min(vals):.4f}\u2013{max(vals):.4f}, "
               f"spread {max(vals) - min(vals):.4f}).\n")

    doc = f"""# Evaluation \u2014 rules vs rules + Gemini

Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by `compare.py`.

The final score is a weighted sum of three metrics:

    final = 0.30 x stage1_macro_f1
          + 0.20 x stage3_defect_f1
          + 0.50 x end_to_end_rate

Everything else below is diagnostic \u2014 it explains those three but does
not contribute to the score.

## Results

| dataset | rules | + Gemini | change | macro-F1 | defect-F1 | end-to-end |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}
{gen}
## Full report

```
{body}
```
"""
    Path(path).write_text(doc, encoding="utf-8")
    _print(f"    wrote {path}")


def find(*names) -> Path:
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    sys.exit(f"Could not find any of {names} in {Path.cwd()}")


BUNDLE = find("sdoc-hackathon-bundle", "bundle")
DOCKER = find("sdoc-hackathon-docker", "docker")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(DOCKER / "server"))
import scoring  # noqa: E402
from sdoc.core.pipeline import FolderSource, run, to_submission  # noqa: E402


# --------------------------------------------------------------------------
# presentation
# --------------------------------------------------------------------------

def header(title: str, width: int = 74) -> None:
    print()
    print("\u250c" + BAR * (width - 2) + "\u2510")
    print("\u2502 " + title.ljust(width - 4) + " \u2502")
    print("\u2514" + BAR * (width - 2) + "\u2518")


def section(title: str) -> None:
    print(f"\n  {title}")
    print("  " + BAR * 70)


def line(name: str, a: float, b: float, weight: float | None = None,
         indent: str = "    ") -> None:
    d = b - a
    delta = "        \u2014" if abs(d) < 1e-9 else f"{d:+9.4f}"
    mark = "" if abs(d) < 1e-9 else ("  \u2191" if d > 0 else "  \u2193")
    w = f"  x{weight:.2f}" if weight else "       "
    print(f"{indent}{name:<22}{a:>10.4f}{b:>11.4f}{delta}{w}{mark}")


def colhead(indent: str = "    ") -> None:
    print(f"{indent}{'':22}{'rules':>10}{'+ Gemini':>11}{'change':>9}{'weight':>8}")


# --------------------------------------------------------------------------
# evaluation
# --------------------------------------------------------------------------

def evaluate(folder: Path, gt_path: Path, llm):
    sub = to_submission(run(FolderSource(folder), llm_classify=llm))
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    return scoring.score_all(gt, sub), sub, gt


def report(label: str, folder: Path, gt_path: Path, llm_fn, show_diff=True):
    header(label)
    r, sub_r, gt = evaluate(folder, gt_path, None)
    l, sub_l, _ = evaluate(folder, gt_path, llm_fn)

    # ---- scored ---------------------------------------------------------
    section("SCORED  \u2014 these three, weighted, are the final score")
    colhead()
    line("stage1 macro-F1", r["stage1"]["macro_f1"], l["stage1"]["macro_f1"], W["stage1"])
    line("stage3 defect-F1", r["stage3"]["defect_f1"], l["stage3"]["defect_f1"], W["stage3"])
    line("end-to-end rate", r["end_to_end"]["rate"], l["end_to_end"]["rate"], W["end_to_end"])
    print("  " + BAR * 70)
    line("FINAL SCORE", r["final_score"], l["final_score"])

    # ---- diagnostic -----------------------------------------------------
    section("DIAGNOSTIC \u2014 explains the above, not scored directly")
    colhead()
    line("stage1 accuracy", r["stage1"]["accuracy"], l["stage1"]["accuracy"])
    line("defect precision", r["stage3"]["defect_precision"], l["stage3"]["defect_precision"])
    line("defect recall", r["stage3"]["defect_recall"], l["stage3"]["defect_recall"])
    line("escalation recall", r["reliability"]["escalation_recall"],
         l["reliability"]["escalation_recall"])
    line("escalation precision", r["reliability"]["escalation_precision"],
         l["reliability"]["escalation_precision"])
    e = l["end_to_end"]
    print(f"    {'e2e emails':<22}{'':>10}{e['success']:>8}/{e['total']:<3}"
          f"   exact defect-field match required")

    # ---- headroom -------------------------------------------------------
    section("HEADROOM \u2014 points still available, by stage")
    gaps = [
        ("stage1 macro-F1", 1.0 - l["stage1"]["macro_f1"], W["stage1"]),
        ("stage3 defect-F1", 1.0 - l["stage3"]["defect_f1"], W["stage3"]),
        ("end-to-end", 1.0 - l["end_to_end"]["rate"], W["end_to_end"]),
    ]
    total = sum(g * w for _, g, w in gaps)
    for name, gap, w in sorted(gaps, key=lambda x: -x[1] * x[2]):
        pts = gap * w
        share = (pts / total * 100) if total else 0
        bar = "\u2588" * int(round(share / 4))
        print(f"    {name:<22}{pts:>8.4f} pts  {share:>5.1f}%  {bar}")
    print("  " + BAR * 70)
    print(f"    {'to a perfect 1.0000':<22}{total:>8.4f} pts")

    # ---- what changed ---------------------------------------------------
    if show_diff:
        fixed, broke = [], []
        for eid, t in gt.items():
            a, b = sub_r[eid]["category"], sub_l[eid]["category"]
            if a != b:
                (fixed if b == t["category"] else broke).append(
                    (eid, t["category"], a, b))
        section("CLASSIFICATION CHANGES")
        if fixed:
            print(f"    fixed  ({len(fixed)}):")
            for eid, want, a, b in fixed[:10]:
                print(f"      {eid}  gold {want:<14} {a} \u2192 {b}")
            if len(fixed) > 10:
                print(f"      ... and {len(fixed) - 10} more")
        if broke:
            print(f"    BROKEN ({len(broke)}):")
            for eid, want, a, b in broke:
                print(f"      {eid}  gold {want:<14} {a} \u2192 {b}")
        if not fixed and not broke:
            print("    none \u2014 rules already settled every email here")
    return r, l


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="*", default=[])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--csv", help="append one row per dataset per mode")
    ap.add_argument("--md", help="save the whole console report as Markdown")
    args = ap.parse_args()

    from sdoc.core.classify import classify as rule_classify
    from sdoc.core.contract import CONFIDENCE_THRESHOLD
    from sdoc.llm.gemini import classify_email, prefetch_classifications, stats

    def warm(folder: Path):
        unsure = [e for e in FolderSource(folder).emails()
                  if rule_classify(e).confidence < CONFIDENCE_THRESHOLD]
        if unsure:
            prefetch_classifications(unsure)

    results = []
    warm(BUNDLE)
    r, l = report("SUPPLIED DATASET  \u00b7  seed 42  \u00b7  520 emails",
                  BUNDLE, DOCKER / "data_v2" / "ground_truth.json", classify_email)
    results.append(("seed42 (supplied)", r, l))

    if args.seeds:
        gen = DOCKER / "data_v2" / "generate.py"
        workdir = Path(tempfile.mkdtemp(prefix="compare_"))
        for seed in args.seeds:
            out = workdir / f"seed_{seed}"
            out.mkdir(parents=True, exist_ok=True)
            p = subprocess.run([sys.executable, str(gen), "--seed", str(seed),
                                "--n", str(args.n), "--out", str(out)],
                               capture_output=True, text=True, timeout=300)
            if p.returncode != 0:
                print(f"  generator failed for seed {seed}: {p.stderr[:200]}")
                continue
            warm(out)
            r, l = report(f"HELD-OUT  \u00b7  seed {seed}  \u00b7  never seen before",
                          out, out / "ground_truth.json", classify_email,
                          show_diff=False)
            results.append((f"seed{seed} (held-out)", r, l))

    # ---- summary --------------------------------------------------------
    header("SUMMARY")
    print(f"    {'dataset':<22}{'rules':>9}{'+ Gemini':>11}{'change':>9}"
          f"{'macroF1':>10}{'e2e':>9}")
    print("  " + BAR * 70)
    for name, r, l in results:
        d = l["final_score"] - r["final_score"]
        ds = "\u2014".rjust(9) if abs(d) < 1e-9 else f"{d:+9.4f}"
        print(f"    {name:<22}{r['final_score']:>9.4f}{l['final_score']:>11.4f}{ds}"
              f"{l['stage1']['macro_f1']:>10.4f}{l['end_to_end']['rate']:>9.4f}")

    held = [l for n, _, l in results if "held-out" in n]
    if held:
        vals = [x["final_score"] for x in held]
        mean = sum(vals) / len(vals)
        spread = max(vals) - min(vals)
        print("  " + BAR * 70)
        print(f"    held-out mean {mean:.4f}   range {min(vals):.4f}\u2013{max(vals):.4f}"
              f"   spread {spread:.4f}")
        base = results[0][2]["final_score"]
        verdict = ("generalises" if mean >= base - 0.03
                   else "WARNING: fitted to the supplied seed")
        print(f"    vs supplied {base:.4f}  \u2192  {verdict}")

    print(f"\n    LLM usage: {stats()}")

    if args.csv:
        import csv
        from datetime import date
        new = not Path(args.csv).exists()
        with open(args.csv, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["date", "dataset", "mode", "final", "macro_f1",
                            "defect_f1", "e2e"])
            today = date.today().isoformat()
            for name, r, l in results:
                for mode, x in (("rules", r), ("rules+llm", l)):
                    w.writerow([today, name.split()[0], mode,
                                round(x["final_score"], 4),
                                round(x["stage1"]["macro_f1"], 4),
                                round(x["stage3"]["defect_f1"], 4),
                                round(x["end_to_end"]["rate"], 4)])
        print(f"    appended to {args.csv}")

    if args.md:
        write_markdown(args.md, results)


if __name__ == "__main__":
    main()