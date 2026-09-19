# Instructions

Shipping document verification — Averis x Monash Hackathon 2026.

## Folder layout

Everything runs from the project root. Don't `cd` into subfolders.

```
SleeplessMonashians Hackathon\
├── run_pipeline.py          main entry point
├── score.py                 score an existing submission
├── verify_setup.py          environment check
├── requirements.txt
├── sdoc\                    the pipeline package
│   └── core\                contract, ingest, extract, classify, normalize, compare, pipeline
├── tests\
├── sdoc-hackathon-bundle\   supplied data
└── sdoc-hackathon-docker\   supplied server + scorer
```

## First-time setup

```powershell
pip install -r requirements.txt
python verify_setup.py
```

`verify_setup.py` must end with `ALL CHECKS PASSED`. It checks the Python
version, both data folders, 520 emails, 250 attachments, the three document
libraries, and whether your OS default encoding mangles the bilingual-label
files. A `[WARN]` about poppler is expected on Windows and is fine.

Everyone on the team runs this. Identical output across machines is what
stops scores diverging later.

## Daily commands

```powershell
python run_pipeline.py                      # run all 520 emails, write submission.json, score it
python run_pipeline.py --email email_013    # inspect one email, with provenance
python run_pipeline.py --report reports.json   # full JSON for the UI
python score.py                             # score submission.json without regenerating
python -m pytest -q                         # unit tests
```

Expected score: **0.9621** on Windows, **0.9753** with poppler installed.
46 tests pass.

## Expected output

`python run_pipeline.py`

```
wrote submission.json  (520 emails)

FINAL SCORE     0.9621
  stage1 macroF1 0.9680   acc 0.9846
  stage3 defF1   0.9670   P 0.978 R 0.957
  end-to-end     0.9565   (44/46)
  escalation     R 0.950 P 1.000
```

`python run_pipeline.py --email email_013`

```
email_013   BL_COMPARISON (conf 0.95, via rule)
  status:   MISMATCH

!!port_of_discharge    mismatch   MOMBASA, KENYA (KEMBA)   TUTICORIN, INDIA (KEMBA)
    SI <- attachments/email_013_SI.txt:10 [Port of Discharge (POD)]
    BL <- attachments/email_013_BL.txt:10 [PORT OF DISCHARGE]
```

## Scoring

Three ways, all reading the same `ground_truth.json` through the same
`scoring.score_all()`. Identical submission bytes always give an identical
score.

```powershell
python score.py                             # everyday use, prints a SHA-256

cd sdoc-hackathon-docker\server              # organizers' own CLI
python score_cli.py ..\..\submission.json
cd ..\..
```

Optional, via the scoring server (needs `fastapi` and `uvicorn`):

```powershell
python run_server.py            # terminal 1
python submit_to_server.py      # terminal 2
```

If two people report different scores, compare the SHA-256 from `score.py`
first. It is almost always two different files, not two different scorers.

## How the pipeline works

```
email  ->  classify  ->  ingest  ->  extract  ->  compare  ->  decide  ->  result
```

Only `BL_COMPARISON` emails go past classification. Each stage takes and
returns the shapes in `sdoc/core/contract.py`; as long as that holds, any
stage can be rewritten without touching the others.

| Module | Owner | Does |
|---|---|---|
| `contract.py` | P | The frozen interface. Changes go through P only. |
| `classify.py` | I | Email body -> one of 5 categories, with confidence |
| `ingest.py` | I | Attachment bytes -> text (txt, pdf, docx, xlsx) |
| `extract.py` | I | Text -> 7 fields, with confidence and source line |
| `normalize.py` | I | Makes values comparable |
| `compare.py` | P | Field verdicts and the escalation decision |
| `pipeline.py` | P | Orchestration and the data-source abstraction |

Confidence: 0.95 for `Label: value`, 0.85 for wide columns, 0.70 for tight
layouts, capped 0.80 for LLM. Below 0.60 the field is escalated rather than
compared. An unreadable value is never reported as a discrepancy.

## Things that will bite you

**Encoding.** 51 text attachments contain `Gross Weight毛重(KGS)`. Always
decode explicitly as UTF-8. The Windows default is cp1252 and drops the
score from 0.96 to 0.58. `sdoc/core/ingest.decode()` handles this — use it
rather than `open()` or `Path.read_text()`.

**Ports.** Compare the port **name**, not the UN/LOCODE. A discrepancy
changes the name and leaves the code unchanged, so normalising to the code
hides 19 of the 46 scoring emails.

**Subjects lie.** Classify on the body. Subject-first scores macro-F1 0.56;
body-first scores 0.97.

**Keywords are sharp.** Adding `BILLING` to the invoice rules cost 15
GENERAL emails instantly. Widen the rules only with a test and a score run.

**Don't tune to the answer key.** `ground_truth.json` shipped in the docker
bundle by accident of packaging; the organizers mount it privately. If they
regenerate the data with a new seed, anything fitted to these 520 emails
breaks. Keep rules driven by the label list, never by email ID.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Score ≈ 0.58 | Attachments read with the OS default encoding |
| Score ≈ 0.92 | `pdfplumber` not installed — PDFs return nothing |
| `ModuleNotFoundError: sdoc` | Run from the project root, not a subfolder |
| `Could not find any of (...)` | Data folders missing or renamed |
| Docker not recognised | Not installed. Use `run_server.py`, or skip it |
| Two machines, two scores | Compare `score.py` hashes before anything else |

## Logging results

After a run that changes the score, append to `SCORES.md`:

```
2026-09-19  0.9621  modular pipeline, confidence + provenance
```

This is evidence for the Technical Feasibility & Validation criterion.
Keep it up to date.