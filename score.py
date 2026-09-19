#!/usr/bin/env python3
"""
score.py — score an EXISTING submission file. Does not regenerate anything.

    python score.py                    # scores submission.json
    python score.py mysubmission.json

Prints the SHA-256 of the file it scored. When a teammate or the Docker
server reports a different number, compare hashes first: identical bytes
always produce an identical score.
"""
import hashlib
import json
import sys
from pathlib import Path


def find(*names):
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    sys.exit(f"Could not find any of {names} in {Path.cwd()}")


DOCKER = find("sdoc-hackathon-docker", "docker")
sys.path.insert(0, str(DOCKER / "server"))
import scoring  # noqa: E402

path = Path(sys.argv[1] if len(sys.argv) > 1 else "submission.json")
if not path.exists():
    sys.exit(f"{path} not found. Run 'python baseline.py' first.")

raw = path.read_bytes()
sub = json.loads(raw)
gt = json.loads((DOCKER / "data_v2" / "ground_truth.json").read_text(encoding="utf-8"))
r = scoring.score_all(gt, sub)

s1, s3, rel, e2e = r["stage1"], r["stage3"], r["reliability"], r["end_to_end"]
print(f"file            {path}")
print(f"sha256          {hashlib.sha256(raw).hexdigest()[:16]}")
print(f"entries         {len(sub)} / {len(gt)}")
missing = [k for k in gt if k not in sub]
if missing:
    print(f"MISSING         {len(missing)} email_ids (scored as defaults) e.g. {missing[:3]}")
print()
print(f"FINAL SCORE     {r['final_score']:.4f}")
print(f"  stage1 macroF1 {s1['macro_f1']:.4f}  x0.30  = {0.30*s1['macro_f1']:.4f}")
print(f"  stage3 defF1   {s3['defect_f1']:.4f}  x0.20  = {0.20*s3['defect_f1']:.4f}")
print(f"  end-to-end     {e2e['rate']:.4f}  x0.50  = {0.50*e2e['rate']:.4f}   ({e2e['success']}/{e2e['total']})")
print()
print(f"  defect precision {s3['defect_precision']:.3f}   recall {s3['defect_recall']:.3f}")
print(f"  escalation       recall {rel['escalation_recall']:.3f}  precision {rel['escalation_precision']:.3f}"
      f"   (gold {rel['gold_review']}, flagged {rel['pred_review']})")
print()
print("  classification errors:")
clean = True
for actual, preds in s1["confusion"].items():
    for pred, n in preds.items():
        if pred != actual:
            print(f"    {n:3} x {actual} -> {pred}")
            clean = False
if clean:
    print("    none")
