# Deployment

For **X**. How to get the current code onto Cloud Run and prove it took.

Live service: **https://sdoc-api-856612571283.asia-southeast1.run.app**

---

## The thing that catches people

Cloud Run serves a **container image** — a frozen copy of the code, taken at
`docker build` time. It does not read your working directory, and it does not
pick up a `git pull`. Until someone rebuilds and redeploys, the URL keeps
serving whatever was built last.

Nothing announces this. The service stays up, returns well-formed JSON, and
quietly gives older answers. On 20 Sep the live URL scored **0.9753** while
the code on `main` scored **0.9995**, and the only way it surfaced was
running the scorer against it.

So: **rebuild after every merge that touches `sdoc/` or `api/`, and verify.**

---

## Deploy

```bash
git pull                       # make sure you have the current code

docker build -t sdoc .

docker tag sdoc \
  asia-southeast1-docker.pkg.dev/PROJECT_ID/REPO/sdoc:latest
docker push \
  asia-southeast1-docker.pkg.dev/PROJECT_ID/REPO/sdoc:latest

gcloud run deploy sdoc-api \
  --image asia-southeast1-docker.pkg.dev/PROJECT_ID/REPO/sdoc:latest \
  --region asia-southeast1 \
  --allow-unauthenticated
```

Substitute the `PROJECT_ID` and `REPO` you used originally.

Or, letting Cloud Build do it in one step:

```bash
gcloud run deploy sdoc-api --source . \
  --region asia-southeast1 --allow-unauthenticated
```

---

## Verify — do not skip this

```powershell
python score_api.py --url https://sdoc-api-856612571283.asia-southeast1.run.app --workers 4
```

A deploy can report success while still serving the old image: wrong tag, a
cached layer, traffic not moved to the new revision. The numbers are the only
proof.

### Current looks like this

```
POST /process ... {'processed': 520, 'needs_review': 19,
                   'mismatches': 46, 'llm_enabled': True}
fetched 520 results in one request (/emails/full)

FINAL SCORE     0.9995
  end-to-end     1.0000   (46/46)
classified: {'rule': 493, 'llm': 27}
```

### Stale looks like this

| Reading | Image predates |
|---|---|
| `mismatches: 48`, defect precision 0.958 | the label-fragment fix in `extract.py` — two false alarms |
| `llm_enabled` missing from the response | the Gemini wiring in `main.py` |
| falls back to 520 individual requests | the `/emails/full` endpoint |
| `needs_review: 22` | poppler missing from the image |
| score 0.9904 not 0.9995 | `.cache/llm/` missing — LLM wired but making live calls |

Each of those is a rebuild away.

---

## What the image must contain

From the `Dockerfile`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY api ./api
COPY sdoc ./sdoc
COPY sdoc-hackathon-bundle ./sdoc-hackathon-bundle
COPY .cache/llm ./.cache/llm
```

Two lines matter more than they look.

**`poppler-utils`** is worth 0.013. Without it pdfplumber takes over, two PDF
pairs escalate instead of being compared, and `needs_review` reads 22 instead
of 19. It degrades into more human review rather than wrong answers, but it
is free to include.

**`.cache/llm`** holds the 27 classifications Gemini has already returned,
keyed by prompt hash. With them, the service reproduces its numbers with **no
API key** and a rate limit cannot break the demo. Without them the service
tries live calls, burns the daily quota, and falls back to rules mid-run.

`.dockerignore` deliberately excludes `docs/`, `tests/`, `*.db` and
`sdoc-hackathon-docker/` — the last is the organisers' scorer and answer key,
which the service never needs.

---

## Configuration

Set as environment variables in the Cloud Run revision.

| Variable | Default in image | Notes |
|---|---|---|
| `SDOC_BUNDLE_PATH` | `/app/sdoc-hackathon-bundle` | |
| `SDOC_DB_PATH` | `/app/data/sdoc.db` | see persistence below |
| `PORT` | `8080` | Cloud Run sets this |
| `SDOC_LLM_MODE` | `live` | `off` disables the fallback |
| `SDOC_GEMINI_MODEL` | `gemini-3.5-flash-lite` | ~500 free requests/day |
| `GEMINI_API_KEY` | — | **not needed**, the cache covers it |

Do not put a key in the image. If one is ever needed, use a Cloud Run secret.

---

## Two known constraints

**Persistence is per-instance.** `data/sdoc.db` lives in the container's
filesystem, so human review decisions are lost when Cloud Run scales to zero
or starts a new instance. Fine for a demo — worth mentioning on the roadmap
slide rather than being asked about it. A volume mount or Cloud SQL would fix
it properly.

**`POST /process` overwrites human decisions.** It reprocesses the inbox from
the source files. Don't run it during a demo after showing a correction.

---

## Region

Currently `asia-southeast1`. Latency from Melbourne is good, but the Cloud Run
always-free tier only applies in `us-central1`, `us-east1` and `us-west1`, so
this runs on trial credit rather than free quota. Fine for the hackathon; just
know it is not free.

---

## Before submitting — Tuesday morning

1. `git pull` on `main`
2. `docker build` → push → `gcloud run deploy`
3. `python score_api.py --url <live> --workers 4` → **0.9995**
4. Open `<live>/docs` in a **logged-out** browser, and on a phone
5. `POST /process`, then `GET /emails/email_013` — must show the
   `port_of_discharge` mismatch with its source lines

A judge opening a stale container sees 0.9753 while the deck claims 0.9995.
That is a worse look than the number itself, and it takes five minutes to
prevent.
