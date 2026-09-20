# Score log

Every entry is one measured run. Always note the environment: a laptop
without poppler reads ~0.013 lower than the container, and the Gemini
fallback is worth another ~0.009.

| date | score | environment | what changed |
|---|---|---|---|
| 2026-09-19 | 0.5831 | laptop | first run — attachments decoded with the OS default encoding |
| 2026-09-19 | 0.9621 | laptop, no poppler | explicit UTF-8 decode + pdfplumber fallback |
| 2026-09-19 | 0.9621 | laptop, no poppler | modular pipeline, confidence + provenance (refactor, no score change) |
| 2026-09-19 | 0.9711 | laptop, no poppler | Gemini fallback — 7 SPAM emails fixed, 0 broken, 2 batched requests |
| 2026-09-20 | 0.9642 | laptop, no poppler | fix: label-fragment false positives on wrapped PDF columns |
| 2026-09-20 | 0.9773 | laptop, no poppler | fix: bilingual-label glyph noise (`Gross Weight<CJK>(KGS)`) |
| 2026-09-20 | 0.9904 | laptop, poppler | poppler text extraction — end-to-end 46/46, defect P/R 1.000 |
| 2026-09-20 | 0.9995 | laptop, poppler | + Gemini fallback — 1 classification error in 520 |
| 2026-09-20 | 0.9995 | API, poppler | Gemini wired into `POST /process`; API and CLI byte-identical, `sha256 b79f3c3d573cd07a` |

## Current

| | no poppler | with poppler |
|---|---|---|
| rules only | 0.9773 | 0.9904 |
| with Gemini | 0.9864 | **0.9995** |

Weighted breakdown at 0.9995:

```
stage1 macro-F1   0.9982  x0.30  = 0.2995
stage3 defect-F1  1.0000  x0.20  = 0.2000
end-to-end        1.0000  x0.50  = 0.5000   (46/46)
```

Defect precision 1.000, recall 1.000. One classification error in 520
(`BL_COMPARISON` read as `INVOICE_QUERY`). 19 emails escalated to human
review.

## Generalisation

Datasets generated with the organisers' own `generate.py` using seeds the
pipeline had never been scored against.

| | |
|---|---|
| held-out mean | **0.9990** |
| range | 0.9984 – 0.9995 |
| spread | 0.0011 |
| end-to-end | 1.0000 on every dataset |
| defect precision / recall | 1.000 on every dataset |

The held-out mean effectively matches the supplied set, so the rules
generalise rather than memorise. `verify_results.py` re-generates fresh
datasets from **random** seeds on every run, so this is re-checked
continuously rather than measured once.

The Gemini fallback also reduces classification variance: macro-F1 across
four datasets goes from 0.9683 ± 0.0113 (rules only) to 0.9965 ± 0.0017 — a
6.5× tighter spread. That, rather than the ~0.009 score gain, is the reason
it is in the system.

Full reports: `docs/RESULTS_deep.md`, `docs/SWEEP.md`, `docs/VERIFY.md`.

## Reproducing

```bash
python verify_results.py                          # 22 checks, ~3 min
python run_pipeline.py --llm                      # 0.9995 with poppler
python compare.py --seeds 7001 7002 --n 500       # rules vs AI, unseen data
python score_api.py                               # score the running service
```

No API key required — the model's previous answers are committed under
`.cache/llm/`.

## Bugs found by measurement

Each was caught by scoring rather than by reading code, and each is in the
history above.

| | cost | found by |
|---|---|---|
| Attachments read with the OS default encoding instead of UTF-8 | 0.38 | first run on Windows |
| Placeholder values (`TBA`, `____MT`) compared as if real, fabricating discrepancies | 2 false alarms | refactor into modules |
| Label fragments captured as values on wrapped PDF columns | 0.015 | held-out seeds at n=500 |
| Bilingual-label glyph noise breaking the match on the pdfplumber path | 0.013 | comparing extractors on one failing file |
| The organisers' `generate.py` defaults `--out` to its own folder, silently overwriting the benchmark | benchmark corrupted twice | checksum in `verify_setup.py` |

## Known limitations

- **Escalation recall 0.95.** `email_501` (`wrong_doc_type`) is reported OK,
  so no reviewer would see it. Not in the scored formula, but "ask for help"
  is a core capability in the brief.
- **No OCR.** Three genuinely scanned PDFs are detected and escalated as
  `unreadable` rather than read. Reading them cannot raise the score — they
  are graded `NEEDS_REVIEW` and we already get them right — so the value
  would be a pre-filled review form, not accuracy.
- **Poppler is optional but worth 0.013.** Without it two PDF pairs escalate
  instead of being compared. It degrades into *more human review*, not into
  wrong answers: defect precision stays at 1.000 either way. The container
  installs `poppler-utils`.
- **Synthetic data.** 0.9990 says the pipeline is correct on this generator,
  not that document verification is solved. The closed label set in
  `pools.py` is a much kinder world than real shipping documents.