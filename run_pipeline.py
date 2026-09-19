#!/usr/bin/env python3
"""
run_pipeline.py — run the modular pipeline over the full inbox.

    python run_pipeline.py                # score + write submission.json
    python run_pipeline.py --out sub.json
    python run_pipeline.py --report reports.json   # full output, for the UI
    python run_pipeline.py --email email_013       # inspect one email

Replaces baseline.py. Same logic, same score, but the stages are now
swappable and every value carries its source.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find(*names) -> Path:
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    sys.exit(f"Could not find any of {names} in {Path.cwd()}\n"
             "Run this from the folder holding the two extracted data folders.")


_transcript: list[str] = []
_print = print


def print(*args, **kwargs):          # noqa: A001 - deliberate shadow
    _print(*args, **kwargs)
    _transcript.append(" ".join(str(a) for a in args))


BUNDLE = find("sdoc-hackathon-bundle", "bundle")
DOCKER = find("sdoc-hackathon-docker", "docker")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sdoc.core.pipeline import FolderSource, process_email, run, to_submission  # noqa: E402


def show_one(email_id: str, source: FolderSource) -> None:
    email = next((e for e in source.emails() if e["email_id"] == email_id), None)
    if email is None:
        sys.exit(f"{email_id} not found")

    r = process_email(email, source)
    print(f"{r.email_id}   {r.classification.category} "
          f"(conf {r.classification.confidence:.2f}, via {r.classification.method})")
    print(f"  evidence: {r.classification.evidence!r}")
    print(f"  status:   {r.status}" + (f"  [{r.review_reason}]" if r.review_reason else ""))
    for n in r.notes:
        print(f"  note:     {n}")
    if not r.comparisons:
        return
    print()
    print(f"  {'FIELD':<20} {'VERDICT':<10} {'SI':<28} {'BL':<28}")
    print("  " + "-" * 86)
    for c in r.comparisons:
        mark = {"mismatch": "!!", "uncertain": "??", "match": "  "}[c.status]
        print(f"{mark}{c.field:<20} {c.status:<10} "
              f"{str(c.si.raw)[:26]:<28} {str(c.bl.raw)[:28]:<28}")
        if c.status == "mismatch":
            print(f"    SI <- {c.si.source.file}:{c.si.source.line} "
                  f"[{c.si.source.label_seen}]")
            print(f"    BL <- {c.bl.source.file}:{c.bl.source.line} "
                  f"[{c.bl.source.label_seen}]")
        if c.reason:
            print(f"    reason: {c.reason}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="submission.json")
    ap.add_argument("--report", help="also write the full result objects here")
    ap.add_argument("--email", help="inspect a single email and exit")
    ap.add_argument("--no-score", action="store_true")
    ap.add_argument("--md", help="save this run's output as Markdown")
    ap.add_argument("--llm", action="store_true",
                    help="enable the Gemini fallback for low-confidence cases")
    args = ap.parse_args()

    source = FolderSource(BUNDLE)

    llm_classify = None
    if args.llm:
        from sdoc.llm.gemini import (classify_email, prefetch_classifications,
                                     stats as llm_stats)
        llm_classify = classify_email

        # Batch the low-confidence cases into a few requests before the main
        # run. Free-tier quotas count REQUESTS, not emails, so this turns ~27
        # calls into ~2. Results land in the cache the per-email hook reads.
        if not args.email:
            from sdoc.core.classify import classify as rule_classify
            from sdoc.core.contract import CONFIDENCE_THRESHOLD
            unsure = [e for e in source.emails()
                      if rule_classify(e).confidence < CONFIDENCE_THRESHOLD]
            if unsure:
                prefetch_classifications(unsure)

    if args.email:
        show_one(args.email, source)
        return

    results = run(source, llm_classify=llm_classify)
    submission = to_submission(results)
    Path(args.out).write_text(json.dumps(submission, indent=1), encoding="utf-8")
    print(f"wrote {args.out}  ({len(submission)} emails)")

    if args.report:
        payload = {eid: r.to_dict() for eid, r in results.items()}
        Path(args.report).write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print(f"wrote {args.report}  (full reports for the UI)")

    if args.no_score:
        return

    sys.path.insert(0, str(DOCKER / "server"))
    import scoring
    gt = json.loads((DOCKER / "data_v2" / "ground_truth.json").read_text(encoding="utf-8"))
    r = scoring.score_all(gt, submission)
    s1, s3, e2e, rel = r["stage1"], r["stage3"], r["end_to_end"], r["reliability"]
    print()
    print(f"FINAL SCORE     {r['final_score']:.4f}")
    print(f"  stage1 macroF1 {s1['macro_f1']:.4f}   acc {s1['accuracy']:.4f}")
    print(f"  stage3 defF1   {s3['defect_f1']:.4f}   P {s3['defect_precision']:.3f} "
          f"R {s3['defect_recall']:.3f}")
    print(f"  end-to-end     {e2e['rate']:.4f}   ({e2e['success']}/{e2e['total']})")
    print(f"  escalation     R {rel['escalation_recall']:.3f} "
          f"P {rel['escalation_precision']:.3f}")
    if args.llm:
        print(f"  llm            {llm_stats()}")

    if args.md:
        from datetime import datetime
        mode = "rules + Gemini fallback" if args.llm else "rules only"
        Path(args.md).write_text(
            f"# Pipeline run\n\n"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')} \u00b7 {mode}\n\n"
            f"```\n" + "\n".join(_transcript).rstrip() + "\n```\n",
            encoding="utf-8")
        _print(f"wrote {args.md}")


if __name__ == "__main__":
    main()