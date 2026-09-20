# API — running and testing

FastAPI service wrapping the pipeline. Nine endpoints, SQLite persistence,
Gemini fallback, human review.

Owner: **X**. The pipeline it calls (`sdoc/`) is owned by P and I.

---

## Two ways to reach it

| | URL | Runs |
|---|---|---|
| **Deployed** | https://sdoc-api-856612571283.asia-southeast1.run.app | a container image, frozen at build time |
| **Local** | http://localhost:8080 | the code in your working directory |

Both serve the same application. They differ whenever the image is older
than the code, which is easy to miss because nothing announces it — the
container simply returns older answers.

**Check before trusting the live one:**

```powershell
python score_api.py --url https://sdoc-api-856612571283.asia-southeast1.run.app --workers 4
```

| Reading | Means |
|---|---|
| `mismatches: 46`, `llm_enabled: true`, "one request", 0.9995 | current |
| `mismatches: 48`, defect precision 0.958 | image predates the label-fragment fix |
| `llm_enabled` absent | image predates the Gemini wiring |
| falls back to 520 requests | image predates `/emails/full` |

Any of the last three means a rebuild is needed — see `docs/DEPLOYMENT.md`.

## Run it locally

```powershell
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8080
```

Wait for `Application startup complete`, then open:

**http://localhost:8080/docs**

That's FastAPI's interactive page — every endpoint with a *Try it out*
button. Far easier than curl, and it's what to demo.

> PowerShell note: `curl` is an alias for `Invoke-WebRequest`, not real curl.
> For POST use `Invoke-RestMethod -Method Post <url>` or `curl.exe`.

---

## Endpoints

| Method | Path | Does |
|---|---|---|
| GET | `/health` | liveness |
| POST | `/process` | run all 520 emails, store results |
| POST | `/process/{email_id}` | reprocess one email (retry) |
| GET | `/emails` | summaries for the inbox list |
| GET | `/emails/full` | every full result in one response |
| GET | `/emails/{email_id}` | one full `EmailResult` |
| GET | `/review-queue` | escalated cases only |
| POST | `/review/{email_id}` | human confirms or corrects |
| GET | `/reviews/{email_id}` | that email's review history |
| GET | `/stats` | counts by category and status |

`/emails/full` is declared **before** `/emails/{email_id}` on purpose —
FastAPI matches routes in order, so otherwise `full` is read as an email id.

---

## Test it in order

### 1. Alive

```
GET /health   ->   {"status": "ok", ...}
```

### 2. Process the inbox

```
POST /process
```

```json
{"processed": 520, "needs_review": 19, "mismatches": 46, "llm_enabled": true}
```

Read those numbers — they tell you the environment:

| | poppler | no poppler |
|---|---|---|
| needs_review | 19 | 22 |
| mismatches | 46 | 45 |

`"llm_enabled": false` means the Gemini fallback didn't load; the service
still works, scoring ~0.013 lower.

### 3. A known discrepancy

```
GET /emails/email_013
```

Must show `MISMATCH` on `port_of_discharge`, `MOMBASA, KENYA (KEMBA)` against
`TUTICORIN, INDIA (KEMBA)`, each with its source file, line number and the
literal label matched.

Note both carry the same UN/LOCODE. Comparing codes instead of names would
call this a match and lose 19 of the 46 scoring emails.

Compare with the CLI — they must agree:

```powershell
python run_pipeline.py --email email_013
```

### 4. The review queue

```
GET /review-queue
```

19 items across four reason codes:

| reason | means |
|---|---|
| `missing_attachment` | a comparison was asked for, documents weren't attached |
| `unreadable` | attachment present, no text recoverable (scanned or corrupt) |
| `wrong_doc_type` | not an SI/BL pair — an invoice or packing list |
| `missing_value` | a required field is blank or a placeholder (`TBA`, `____MT`) |

Demo all four, not just one. They tell a much better story together.

### 5. The review loop — persistence

The test that matters most, because the eval cannot measure it. Verified
working; re-run it after any change to `api/storage.py`.

1. `GET /review-queue`, take an `email_id`
2. `POST /review/{email_id}`:
   ```json
   {"action": "correct", "field": "notify_party", "corrected_value": "ACME CO LTD"}
   ```
   `{"action": "confirm"}` also works, with no field.
3. `GET /emails/{email_id}` — status flips to `OK`, `review_reason` clears,
   and a note is appended:
   `"Human reviewer supplied notify_party: ACME CO LTD."`
4. **Ctrl-C uvicorn, start it again**
5. `GET /emails/{email_id}` — the correction is still there
6. `GET /review-queue` — now 18, was 19
7. `GET /reviews/{email_id}` — the audit row, with a timestamp

Do **not** run `POST /process` between steps 3 and 5. It reprocesses the
whole inbox from the source files and overwrites human decisions. Known
limitation; a reprocess should ideally preserve them.

#### Where it is stored

`data/sdoc.db` (gitignored — rebuilt by `POST /process`):

```sql
results (email_id PRIMARY KEY, result_json, updated_at)
reviews (id, email_id, field, corrected_value, action, created_at)
```

`results` is current state; `reviews` is an append-only audit trail.
`update_result_after_review()` applies the correction into `comparisons[]`
where one exists, and falls back to `human_corrections{}` when the escalation
happened before any comparison could be made — an unreadable or missing
document, for instance.

---

## Prove the API matches the CLI

```powershell
python score_api.py
```

Pulls every result from the running service, scores it with the organisers'
own `scoring.py`, and reports whether the model was used:

```
  FINAL SCORE     0.9995
    end-to-end     1.0000   (46/46)
  classified: {'rule': 493, 'llm': 27}
  Gemini fallback IS active (27 emails classified by model).
```

Then run the CLI **the same way** and compare checksums:

```powershell
python run_pipeline.py --llm --out submission_local.json
python score.py submission_api.json
python score.py submission_local.json
```

Identical SHA-256 means the deployed service is the pipeline, not a
reimplementation that happens to agree. Verified: `b79f3c3d573cd07a`.

Only two things legitimately change the hash:
- the `--llm` flag not matching how the API ran
- poppler present in one terminal but not the other

Against a deployed service:

```powershell
python score_api.py --url https://sdoc-api-856612571283.asia-southeast1.run.app --workers 4
python score_api.py --url https://sdoc-api-856612571283.asia-southeast1.run.app --no-process --workers 4
```

Use `--workers 4` against Cloud Run; the free tier is a single instance and
does not like 16 concurrent requests.

---

## Expected scores

| | no poppler | with poppler |
|---|---|---|
| rules only | 0.9773 | 0.9904 |
| with Gemini | 0.9864 | **0.9995** |

The container installs `poppler-utils`, so the deployed service is always in
the right-hand column. Locally, unzip poppler anywhere under your home folder
and it's found automatically — `python verify_setup.py` prints where.

---

## Configuration

| Variable | Default | Does |
|---|---|---|
| `SDOC_BUNDLE_PATH` | `sdoc-hackathon-bundle` | where the dataset lives |
| `SDOC_DB_PATH` | `data/sdoc.db` | SQLite file |
| `SDOC_LLM_MODE` | `live` | `off` disables the fallback |
| `SDOC_GEMINI_MODEL` | `gemini-3.5-flash-lite` | ~500 free requests/day |
| `GEMINI_API_KEY` | — | **not needed**, see below |
| `SDOC_POPPLER_PATH` | — | poppler bin dir, if in an unusual place |

**No API key is required.** The 27 classifications the model already returned
are committed under `.cache/llm/` and copied into the image, so the service
reproduces its numbers offline and a rate limit cannot break the demo.

---

## Docker

```powershell
docker build -t sdoc .
docker run -p 8080:8080 sdoc
python score_api.py --url http://localhost:8080
```

Expect **0.9995** — the image installs poppler, so it scores higher than a
bare laptop.

The image includes `sdoc/`, `api/`, the dataset and `.cache/llm/`. It excludes
`docs/`, `tests/`, `*.db` and the organisers' scoring folder.

---

## Notes for the frontend

- **List view** uses `GET /emails` (summaries). Do not fetch 520 full
  objects to render a list — each is ~8 KB and it took 68 seconds before
  `/emails/full` existed.
- **Detail view** fetches `GET /emails/{id}` when a row is opened.
- `comparisons[]` is what the report screen renders: seven fields, each with
  `status`, `si`, `bl`, and `source` (file, line, `label_seen`, `snippet`).
- `defect_fields` lists **confirmed** discrepancies only, so it is empty on a
  `NEEDS_REVIEW` email. Unverified differences are in
  `unconfirmed_mismatches` — show them differently, since the system has not
  stood behind them.
- CORS is open (`allow_origins=["*"]`), fine for the hackathon.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Unable to connect` | server not running, or still starting |
| `404 ... has not been processed` | run `POST /process` first |
| `needs_review: 22` | poppler not found by the server process |
| live differs from local | the deployed image is stale — rebuild, see `docs/DEPLOYMENT.md` |
| `llm_enabled: false` | `google-genai` missing, or `SDOC_LLM_MODE=off` |
| hashes differ vs CLI | `--llm` mismatch, or poppler in only one terminal |
| `/emails/full` 404s | route declared after `/emails/{email_id}` |
