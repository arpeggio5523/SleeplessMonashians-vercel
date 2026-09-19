# Instructions

Shipping document verification — Averis x Monash Hackathon 2026.

Current: **0.9904** rules only, **0.9995** with the Gemini fallback (with
poppler). Held-out mean **0.9990** across five unseen datasets.

## Layout

Everything runs from the project root. Don't `cd` into subfolders.

```
SleeplessMonashians Hackathon/
├── sdoc/                      the pipeline package
│   ├── core/                  contract, ingest, extract, classify,
│   │                          normalize, compare, pipeline
│   └── llm/                   Gemini fallback
├── api/                       FastAPI service            (X)
├── web/                       React frontend             (U)
├── tests/                     46 unit tests
├── docs/                      evidence: RESULTS, SWEEP, CSVs
├── .cache/llm/                27 cached classifications — COMMITTED
│
├── run_pipeline.py            main entry point
├── compare.py                 rules vs rules+LLM, with headroom analysis
├── sweep.py                   score across freshly generated datasets
├── score.py                   score an existing submission (prints SHA-256)
├── verify_setup.py            environment + benchmark integrity check
├── check_gemini.py            prove the API key and model work
├── run_server.py              organisers' scoring server, without Docker
├── submit_to_server.py        POST a submission to it
│
├── README.md                  ← mandatory deliverable, X owns
├── SCORES.md                  dated score log
├── TEAM_PLAN.md               roles and stages
├── instructions.md            this file
├── requirements.txt
├── Dockerfile                 (X)
│
├── sdoc-hackathon-bundle/     supplied data      — gitignored
└── sdoc-hackathon-docker/     supplied server    — gitignored
```

The two supplied folders are **not committed**. `sdoc-hackathon-docker`
contains `ground_truth.json`, the answer key; it should not sit in a public
repo that judges will read. Extract the organisers' zips locally.

## Setup

```powershell
pip install -r requirements.txt
python verify_setup.py
```

Must end with `ALL CHECKS PASSED`. It checks Python, both data folders, 520
emails, 250 attachments, the document libraries, the OS encoding trap, and
the SHA-256 of `ground_truth.json`.

### poppler (recommended, worth ~0.013)

No installer needed; a session-scoped PATH entry is enough.

```powershell
$dst = "$env:USERPROFILE\poppler"
$rel = Invoke-RestMethod "https://api.github.com/repos/oschwartz10612/poppler-windows/releases/latest"
$url = ($rel.assets | Where-Object { $_.name -like "Release-*.zip" } | Select-Object -First 1).browser_download_url
Invoke-WebRequest $url -OutFile "$env:TEMP\poppler.zip"
Expand-Archive "$env:TEMP\poppler.zip" -DestinationPath $dst -Force
$env:PATH += ";" + (Get-ChildItem -Recurse -Filter pdftotext.exe $dst | Select-Object -First 1).DirectoryName
where.exe pdftotext
```

The container installs it properly via `poppler-utils`.

### Gemini (optional — the cache is committed)

```powershell
pip install google-genai
$env:GEMINI_API_KEY="your-key"        # free at https://aistudio.google.com/apikey
$env:SDOC_GEMINI_MODEL="gemini-3.5-flash-lite"
python check_gemini.py
```

Flash-Lite allows ~500 requests/day; the full Flash models allow ~20. Because
`.cache/llm/` is committed, `--llm` works with no key at all.

## Commands

Every command below states exactly what it writes, so nothing is a surprise
and `.gitignore` can be reasoned about.

### Daily

```powershell
python run_pipeline.py
```
writes `submission.json` (520 entries, ~60 KB, **committed** — it is the
deliverable). Prints the score. Expect **0.9904** with poppler, 0.9773 without.

```powershell
python run_pipeline.py --llm
```
writes `submission.json`; reads `.cache/llm/` and writes any new entries there.
Expect **0.9995** with poppler, 0.9864 without.

```powershell
python run_pipeline.py --email email_013
```
writes nothing. Prints one email with its seven fields, the verdict, and the
source file and line behind each value.

```powershell
python run_pipeline.py --report docs\reports.json
```
writes `submission.json` **and** `docs/reports.json` (~1.4 MB, **gitignored**)
— the full `EmailResult` for all 520 emails. This is what U builds the
frontend against.

```powershell
python score.py
```
writes nothing. Reads the existing `submission.json`, prints its SHA-256 and
the weighted breakdown. Use this when two machines disagree: compare hashes
before anything else.

```powershell
python -m pytest -q
```
writes `.pytest_cache/` (**gitignored**). Expect `46 passed`.

### Validation

```powershell
python compare.py --seeds 7001 7002 7003 --n 500 --md docs\RESULTS.md --csv docs\compare.csv
```
writes `docs/RESULTS.md` (**committed** — evidence) and appends to
`docs/compare.csv` (**committed**). Generates each dataset into a temp folder
and deletes it afterwards. Uses ~6 batched Gemini requests, or zero if the
cache already covers them.

```powershell
python sweep.py --seeds 7001 7002 7003 --n 500 --md docs\SWEEP.md --csv docs\sweep.csv
```
writes `docs/SWEEP.md` and `docs/sweep.csv` (**committed**). Add `--keep` to
leave the generated datasets in `heldout/` (**gitignored**) instead of a temp
folder.

### Setup checks

```powershell
python verify_setup.py
```
writes nothing. Exits non-zero with a specific fix for each problem.

```powershell
python check_gemini.py
```
writes nothing. Lists the models your key can reach, makes one call, and
validates the JSON parses.

### Scoring server (optional)

```powershell
python run_server.py          # terminal 1 — serves http://localhost:8080
python submit_to_server.py    # terminal 2 — POSTs submission.json
```
writes nothing. Must print the same score as `score.py` for the same file.

### Expected scores

| Run | no poppler | with poppler |
|---|---|---|
| rules only | 0.9773 | 0.9904 |
| `--llm` | 0.9864 | 0.9995 |

### What lands where

| Path | Committed? | Rebuilt by |
|---|---|---|
| `submission.json` | yes | `run_pipeline.py` |
| `.cache/llm/*.json` | yes — so the demo needs no API key | `run_pipeline.py --llm` |
| `docs/RESULTS.md`, `docs/SWEEP.md`, `docs/*.csv` | yes — validation evidence | `compare.py`, `sweep.py` |
| `docs/reports.json` | no, 1.4 MB | `run_pipeline.py --report` |
| `heldout/`, `.pytest_cache/`, `__pycache__/` | no | the commands above |

## How it works

```
email -> classify -> ingest -> extract -> compare -> decide -> result
```

Only `BL_COMPARISON` emails go past classification. Each stage takes and
returns the shapes in `sdoc/core/contract.py`; while that holds, any stage
can be rewritten without touching the others.

| Module | Owner | Does |
|---|---|---|
| `contract.py` | P | The frozen interface. Changes go through P only. |
| `classify.py` | I | Email body -> one of 5 categories, with confidence |
| `ingest.py` | I | Attachment bytes -> text (txt, pdf, docx, xlsx) |
| `extract.py` | I | Text -> 7 fields, with confidence and source line |
| `normalize.py` | I | Makes values comparable |
| `llm/gemini.py` | I | Batched fallback when rules are unsure |
| `compare.py` | P | Field verdicts and the escalation decision |
| `pipeline.py` | P | Orchestration and the data-source abstraction |

Confidence: 0.95 `Label: value`, 0.85 wide columns, 0.80 wrapped value, 0.70
tight layout, capped 0.80 for the LLM. Below 0.60 a field escalates rather
than being compared. **An unreadable value is never a discrepancy** — that is
what keeps defect precision at 1.000.

Rules settle 493 of 520 emails; only the 27 below threshold reach Gemini, and
those go in 2 batched requests, not 27 calls.

## Things that will bite you

**`generate.py` defaults `--out` to its own folder.** Running it without
`--out` overwrites the supplied dataset *and* its ground truth, silently.
`verify_setup.py` checksums it. To restore:
`python sdoc-hackathon-docker\data_v2\generate.py --seed 42 --n 500 --out sdoc-hackathon-docker\data_v2`

**Encoding.** 51 text attachments contain `Gross Weight毛重(KGS)`. Always
decode explicitly as UTF-8 — the Windows default drops the score to 0.58.
Use `sdoc/core/ingest.decode()`, never bare `open()`.

**Ports.** Compare the port **name**, not the UN/LOCODE. A discrepancy
changes the name and leaves the code alone, so matching on the code hides
19 of the 46 scoring emails.

**Subjects lie.** Classify on the body. Subject-first scores macro-F1 0.56.

**Keywords are sharp.** Adding `BILLING` to the invoice rules cost 15 GENERAL
emails instantly. Widen rules only with a test and a sweep.

**Placeholders aren't values.** `TBA`, `???`, `____MT` mean "not filled in".
Comparing them fabricates discrepancies.

**Don't tune to the answer key.** Check every change against a fresh seed.
If seed 42 rises while the held-out mean falls, revert.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Score ≈ 0.58 | Attachments read with the OS default encoding |
| Score ≈ 0.92 | `pdfplumber` not installed — PDFs return nothing |
| Score ≈ 0.977 vs 0.990 | poppler not on PATH; expected on a bare laptop |
| Ground-truth checksum fails | `generate.py` ran without `--out` |
| `ModuleNotFoundError: sdoc` | Run from the project root |
| `docker: not recognized` | Not installed. Use `run_server.py` |
| 429 daily quota | Per model. Switch to `gemini-3.5-flash-lite` |
| Two machines, two scores | Compare `score.py` hashes first |

## Before every PR

```powershell
python run_pipeline.py
python -m pytest -q
```

Both must pass. State the score in the PR if it moved, and add a line to
`SCORES.md` with the environment noted.
