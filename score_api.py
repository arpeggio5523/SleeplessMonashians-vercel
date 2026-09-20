#!/usr/bin/env python3
"""
score_api.py — pull results from the RUNNING API and score them, so you can
prove the deployed service produces the same numbers as the local pipeline.

    # terminal 1
    uvicorn api.main:app --port 8080
    # terminal 2
    python score_api.py
    python score_api.py --url https://your-cloud-run-url

It also reports whether the service is using the Gemini fallback, by counting
how many classifications came from the model rather than the rules.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def find(*names) -> Path:
    for n in names:
        p = Path(n)
        if p.is_dir():
            return p
    sys.exit(f"Could not find any of {names} in {Path.cwd()}")


DOCKER = find("sdoc-hackathon-docker", "docker")
sys.path.insert(0, str(DOCKER / "server"))
import scoring  # noqa: E402


def get(url: str, timeout: int = 300):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach {url}\n  {e}\n"
                 "  Is the server running?  uvicorn api.main:app --port 8080")


def post(url: str, timeout: int = 600):
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        sys.exit(f"POST {url} failed\n  {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8080")
    ap.add_argument("--no-process", action="store_true",
                    help="skip POST /process and score whatever is stored")
    ap.add_argument("--workers", type=int, default=16,
                    help="parallel fetches (default 16; lower it if the "
                         "server struggles)")
    args = ap.parse_args()
    base = args.url.rstrip("/")

    print(f"  api: {base}")
    print(f"  health: {get(base + '/health')}")

    if not args.no_process:
        print("  POST /process ... (a few seconds)", end="", flush=True)
        r = post(base + "/process")
        print(f" {r}")

    # One request for everything, when the server supports it.
    fetched = None
    try:
        bulk = get(base + "/emails/full", timeout=300)
        results = bulk.get("results") or []
        if results:
            fetched = [(r["email_id"], r) for r in results]
            print(f"  fetched {len(fetched)} results in one request "
                  f"(/emails/full)")
    except SystemExit:
        pass          # older server without the bulk endpoint

    listing = get(base + "/emails")
    ids = [e["email_id"] for e in listing["emails"]]

    # 520 sequential requests each open a new TCP connection, which is slow.
    # Fetch in parallel instead; the API is read-only here so order does not
    # matter.
    t0 = time.time()
    done = [0]


    def fetch(eid: str):
        d = get(f"{base}/emails/{eid}", timeout=60)
        done[0] += 1
        n = done[0]
        if n % 25 == 0 or n == len(ids):
            pct = n / len(ids)
            bar = "#" * int(pct * 30)
            print(f"\r  fetching {n}/{len(ids)} [{bar:<30}] "
                  f"{time.time() - t0:.0f}s", end="", flush=True)
        return eid, d

    if fetched is None:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            fetched = list(pool.map(fetch, ids))
        print()

    submission, methods, statuses = {}, Counter(), Counter()
    for eid, d in fetched:
        cls = d.get("classification") or {}
        methods[cls.get("method", "?")] += 1
        statuses[d.get("status")] += 1
        submission[eid] = {
            "category": cls.get("category"),
            "status": d.get("status"),
            "review_reason": d.get("review_reason"),
            "has_defect": d.get("has_defect", False),
            "defect_fields": d.get("defect_fields", []),
        }

    gt = json.loads((DOCKER / "data_v2" / "ground_truth.json")
                    .read_text(encoding="utf-8"))
    s = scoring.score_all(gt, submission)

    print()
    print(f"  FINAL SCORE     {s['final_score']:.4f}")
    print(f"    stage1 macroF1 {s['stage1']['macro_f1']:.4f}")
    print(f"    stage3 defF1   {s['stage3']['defect_f1']:.4f}")
    print(f"    end-to-end     {s['end_to_end']['rate']:.4f}"
          f"   ({s['end_to_end']['success']}/{s['end_to_end']['total']})")
    print()
    print(f"  statuses:   {dict(statuses)}")
    print(f"  classified: {dict(methods)}")

    llm_used = methods.get("llm", 0)
    print()
    if llm_used:
        print(f"  Gemini fallback IS active ({llm_used} emails classified by model).")
    else:
        print("  Gemini fallback is NOT active — every classification came from")
        print("  the rules. api/main.py calls run(source) without llm_classify.")
        print("  Expect ~0.9904 rather than ~0.9995 (with poppler).")

    Path("submission_api.json").write_text(
        json.dumps(submission, indent=1), encoding="utf-8")

    # The local run has to be made the SAME WAY as the API run, or the two
    # files differ for a reason that has nothing to do with the API. The API
    # used the model on this run iff any classification came back method=llm.
    flag = " --llm" if llm_used else ""
    print()
    print("  wrote submission_api.json")
    print()
    print("  To prove the API and the CLI agree byte for byte, run the CLI the")
    if llm_used:
        print("  same way - the API used the Gemini fallback, so pass --llm:")
    else:
        print("  same way - the API used rules only, so omit --llm:")
    print()
    print(f"    python run_pipeline.py{flag} --out submission_local.json")
    print("    python score.py submission_api.json")
    print("    python score.py submission_local.json")
    print()
    print("  Identical SHA-256 means they agree exactly. If the hashes differ,")
    print("  check these before anything else:")
    print(f"    - the --llm flag matches ({'used' if llm_used else 'not used'} by the API)")
    print("    - poppler is present in BOTH the uvicorn terminal and this one")
    print("      (python verify_setup.py prints where it was found)")


if __name__ == "__main__":
    main()