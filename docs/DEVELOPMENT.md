# Development

Internal working reference. For the project overview, quick start and
results, read `README.md` first. For running and testing the service, see
`api/API_TESTING.md`.

Everything below runs from the project root.

---

## Layout

```
SleeplessMonashians Hackathon/
├── sdoc/                      the pipeline
│   ├── core/                  contract, classify, ingest, extract,
│   │                          normalize, compare, pipeline
│   └── llm/                   Gemini fallback
├── api/                       FastAPI service + SQLite         (X)
├── web/                       frontend                         (U)
├── tests/                     46 unit tests
├── docs/                      validation evidence
├── .cache/llm/                27 cached classifications — COMMITTED
│
├── verify_results.py          ONE-COMMAND CHECK — start here
├── run_pipeline.py            main entry point
├── compare.py                 rules vs rules+LLM, with headroom analysis
├── sweep.py                   score across freshly generated datasets
├── score.py                   score an existing submission (prints SHA-256)
├── score_api.py               score the RUNNING service
├── verify_setup.py            environment + benchmark integrity
├── check_gemini.py            prove the API key and model work
│
├── sdoc-hackathon-bundle/     supplied data      — committed
└── sdoc-hackathon-docker/     supplied scorer    — committed
```

---

## Commands, and what each writes

Nothing here needs a Gemini API key; `.cache/llm/` is committed.

### Checks

```powershell
python verify_results.py
```
writes nothing (unless `--md`). 22 checks: environment, benchmark checksum,
pipeline score, unit tests, rules-vs-Gemini comparison, and datasets
generated from **random** seeds. Exits non-zero on failure.

```powershell
python verify_results.py --quick              # ~20s, skips generation
python verify_results.py --unseen 10 --n 800  # ~15 min, 8,000 emails
python verify_results.py --seed-base 42       # reproducible seeds
python verify_results.py --llm                # AI on the unseen data too (needs a key)
python verify_results.py --md docs\VERIFY.md  # save the report
```

```powershell
python verify_setup.py
```
writes nothing. Environment and data only — the first two sections of the
above. Prints where poppler was found.

### Running the pipeline

```powershell
python run_pipeline.py
```
writes `submission.json` (**committed** — it is the deliverable). Prints the
score. 0.9904 with poppler, 0.9773 without.

```powershell
python run_pipeline.py --llm
```
same, with the Gemini fallback. 0.9995 / 0.9864.

```powershell
python run_pipeline.py --email email_013
```
writes nothing. One email: seven fields, the verdict, and the source file
and line behind each value.

```powershell
python run_pipeline.py --report docs\reports.json
```
writes `submission.json` **and** `docs/reports.json` (~1.4 MB,
**gitignored**) — every `EmailResult` in full. The frontend fixture.

```powershell
python score.py [file]
```
writes nothing. Scores an existing submission and prints its SHA-256.

### Validation

```powershell
python compare.py --seeds 7001 7002 7003 --n 500 --md docs\RESULTS.md --csv docs\compare_poppler.csv
```
Rules vs rules+Gemini on the supplied set and on freshly generated ones.
Shows which emails the model changed and where the remaining points are.
Generated data goes to a temp folder and is deleted.

```powershell
python sweep.py --seeds 9111 9222 9333 --n 500 --md docs\SWEEP.md
```
Rules only, so any seeds are free. Reports standard deviation, which
`compare.py` does not. `--keep` leaves the data in `heldout/` (gitignored).

```powershell
python score_api.py                                    # local uvicorn
python score_api.py --url https://sdoc-api-856612571283.asia-southeast1.run.app --workers 4
```
writes `submission_api.json` (**gitignored**). Pulls every result from the
running service, scores it, and reports whether the model was used.

**The deployed service runs a container image, not your working copy.** It
only changes when someone rebuilds and redeploys. A stale image returns
plausible-looking older answers with nothing to announce it, so run this
against the live URL after every deploy — and again before submitting.
`docs/DEPLOYMENT.md` has the procedure.

### Tests

```powershell
python -m pytest -q
```
writes `.pytest_cache/` (gitignored). Expect `46 passed`.

### What lands where

| Path | Committed? | Rebuilt by |
|---|---|---|
| `submission.json` | yes | `run_pipeline.py` |
| `.cache/llm/*.json` | yes — so nothing needs an API key | `run_pipeline.py --llm` |
| `docs/RESULTS*.md`, `SWEEP.md`, `VERIFY.md`, `compare_poppler.csv` | yes — evidence | `compare.py`, `sweep.py`, `verify_results.py` |
| `docs/reports.json` | no, 1.4 MB | `run_pipeline.py --report` |
| `data/sdoc.db` | no, runtime state | `POST /process` |
| `submission_api.json` | no, scratch | `score_api.py` |
| `heldout/`, `.pytest_cache/`, `__pycache__/` | no | the commands above |

---

## How the pipeline works

```
email -> classify -> ingest -> extract -> compare -> decide -> result
```

Only `BL_COMPARISON` emails go past classification. Each stage takes and
returns the shapes in `sdoc/core/contract.py`; while that holds, any stage
can be rewritten without touching the others.

| Module | Owner | Does |
|---|---|---|
| `contract.py` | P | **FROZEN.** Changes go through P only. |
| `classify.py` | I | email body -> one of 5 categories, with confidence |
| `ingest.py` | I | attachment bytes -> text (txt, pdf, docx, xlsx) |
| `extract.py` | I | text -> 7 fields, with confidence and source line |
| `normalize.py` | I | makes values comparable |
| `llm/gemini.py` | I | batched fallback when the rules are unsure |
| `compare.py` | P | field verdicts and the escalation decision |
| `pipeline.py` | P | orchestration, data-source abstraction |
| `api/` | X | service, persistence, review endpoints |

### Confidence tiers

| | how the value was found |
|---|---|
| 0.95 | `Label: value` |
| 0.85 | `Label␣␣␣␣value` — wide column |
| 0.80 | label alone on its line, value wrapped to the next |
| 0.70 | `Label␣value` — tight layout |
| ≤0.80 | recovered by the model (capped, so a guess never outranks a rule) |

Below **0.60** a field is escalated rather than compared. **An unreadable
value is never reported as a discrepancy** — that is what keeps defect
precision at 1.000.

### Escalation

Uncertainty outranks mismatch: if any field could not be read, the whole
email is escalated rather than reporting a partial comparison.

| reason | means |
|---|---|
| `missing_attachment` | a comparison was asked for, documents weren't attached |
| `unreadable` | attachment present, no text recoverable |
| `wrong_doc_type` | not an SI/BL pair |
| `missing_value` | a required field is blank or a placeholder |

`defect_fields` holds **confirmed** discrepancies only, so it is empty on a
`NEEDS_REVIEW` email. Unverified differences go in `unconfirmed_mismatches`.

A reviewer's decision is stored in `data/sdoc.db` and survives a restart
(verified). But `POST /process` reprocesses the inbox from the source files
and overwrites human decisions — known limitation, noted in
`api/API_TESTING.md`.

---

## Traps

Each of these cost us real time. They are in `SCORES.md` with what they cost.

**`generate.py` defaults `--out` to its own folder.** Running it without
`--out` silently overwrites the supplied dataset *and* its ground truth, and
every score afterwards measures something else. It has happened twice.
`verify_setup.py` checksums the ground truth and catches it. Restore with:

```powershell
python sdoc-hackathon-docker\data_v2\generate.py --seed 42 --n 500 --out sdoc-hackathon-docker\data_v2
```

**Encoding.** 51 text attachments contain `Gross Weight毛重(KGS)`. Decode
explicitly as UTF-8 — the Windows default drops the score to 0.58. Use
`sdoc.core.ingest.decode()`, never a bare `open()`.

**Ports.** Compare the port **name**, never the UN/LOCODE. A discrepancy
changes the name and leaves the code alone, so matching on the code hides 19
of the 46 scoring emails. There is a test guarding this.

**Subjects lie.** Classify on the body. Subject-first scores macro-F1 0.56;
body-first scores 0.97.

**Keywords are sharp.** Adding `BILLING` to the invoice rules cost 15
GENERAL emails instantly. Widen rules only with a test and a sweep.

**Placeholders aren't values.** `TBA`, `???`, `____MT`, `N/A` mean "not
filled in". Comparing them fabricates discrepancies.

**Label fragments.** In wide PDF columns a long label can fill the line with
its value wrapped below. A loose pattern then captures the *rest of the
label* as a value. Guarded by `_is_label_fragment()`.

**Don't tune to the answer key.** Check every change against fresh seeds. If
seed 42 rises while the held-out mean falls, revert.

---

## poppler

Found automatically — PATH first, then `~/poppler`, `C:\poppler`,
`/usr/local/bin` and the usual places, including nested
`poppler-xx.xx.x/Library/bin` layouts. **No PATH edit needed:** unzip it
anywhere under your home folder. `SDOC_POPPLER_PATH` overrides.

`python verify_setup.py` prints where it was found. The container installs
`poppler-utils`, so the deployed service always has it.

Worth 0.013. Without it, two PDF pairs escalate instead of being compared —
more human review, not wrong answers.

---

## Gemini

Rules settle 493 of 520 emails; only the 27 below threshold reach the model,
and those go in **2 batched requests**, not 27 calls. Results are cached by
prompt hash under `.cache/llm/`, which is committed — so nothing needs a key.

A key is only needed for prompts nobody has run: a new seed, or after editing
the prompt (which invalidates the cache by design).

```powershell
$env:GEMINI_API_KEY="your-own-key"          # https://aistudio.google.com/apikey
$env:SDOC_GEMINI_MODEL="gemini-3.5-flash-lite"
python check_gemini.py
```

Use **your own** key — quotas are per Google Cloud project, so a shared key
means a shared limit. Flash-Lite allows ~500 requests/day; the full Flash
models ~20. If you run new seeds with a key, commit the resulting
`.cache/llm/*.json` so nobody pays for the same calls twice.

The model never compares documents. It classifies an email or recovers a
field the rules could not find. Comparison stays deterministic.

---

## Working rules

- Branch `feat/<role>-<thing>`. PR to `main`. **Only P merges.**
- Before every PR: `python verify_results.py --quick` must pass. State the
  score in the PR if it moved, and add a line to `SCORES.md` noting the
  environment.
- `contract.py` is frozen. Need a change? Ask P. **Add** fields, never
  rename — renames break everyone downstream.
- Never copy `sdoc-hackathon-docker/` out of a teammate's zip; that is how
  the benchmark got overwritten. Re-extract the organisers' original, or use
  the restore command above.
- Never commit: API keys, `.env`, service-account JSON.
- Any push touching `sdoc/` or `api/` needs a **rebuild and redeploy**, then
  `python score_api.py --url <live>` to confirm it took. A container does not
  pick up code changes on its own.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Score ≈ 0.58 | attachments read with the OS default encoding |
| Score ≈ 0.92 | `pdfplumber` not installed — PDFs return nothing |
| 0.9773 vs 0.9904 | poppler not found; expected on a bare laptop |
| Ground-truth checksum fails | `generate.py` ran without `--out` |
| `ModuleNotFoundError: sdoc` | run from the project root |
| `llm_enabled: false` | `google-genai` missing, or `SDOC_LLM_MODE=off` |
| 429 daily quota | per model — switch to `gemini-3.5-flash-lite` |
| Two machines, two scores | compare `score.py` hashes first |
| API hash ≠ CLI hash | `--llm` mismatch, or poppler in only one terminal |
| live URL ≠ local uvicorn | the deployed image is stale — rebuild and redeploy |
