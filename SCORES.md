# Score log

Every entry is one measured run of `python run_pipeline.py`. Always note the
environment: laptop without poppler reads ~0.013 lower than the container.

| date | score | environment | what changed |
|---|---|---|---|
| 2026-09-19 | 0.5831 | laptop | first run — attachments decoded with the OS default encoding |
| 2026-09-19 | 0.9621 | laptop, no poppler | explicit UTF-8 decode + pdfplumber fallback |
| 2026-09-19 | 0.9621 | laptop, no poppler | modular pipeline, confidence + provenance (refactor, no score change) |
| 2026-09-19 | 0.9711 | laptop, no poppler | Gemini fallback — 7 SPAM emails fixed, 0 broken, 2 batched requests |
| 2026-09-20 | 0.9642 | laptop, no poppler | fix: label-fragment false positives on wrapped PDF columns |
| 2026-09-20 | 0.9773 | laptop, no poppler | fix: bilingual-label glyph noise (`Gross Weight<CJK>(KGS)`) |
| 2026-09-20 | 0.9904 | laptop, poppler | poppler text extraction — end-to-end 46/46, defect P/R 1.000 |
| 2026-09-20 | 0.9995 | laptop, poppler | + Gemini fallback — 1 classification error in 520 emails |

## Generalisation

Five datasets generated with seeds the pipeline had never seen
(`python compare.py --seeds 7001 7002 7003 7004 7005 --n 500`):

| | |
|---|---|
| held-out mean | **0.9990** |
| range | 0.9984 – 0.9995 |
| spread | 0.0011 |
| end-to-end | 1.0000 on all five |
| defect precision / recall | 1.000 on all five |

Full detail in `docs/RESULTS_deep.md`.

## Known limitations

- Escalation recall 0.85–0.95. `email_501` (`wrong_doc_type`) is reported OK,
  so no human would see it. Not in the scored formula, but human-in-the-loop
  is a core capability in the brief.
- No OCR. The three genuinely scanned PDFs are detected and escalated as
  `unreadable` rather than read.
- Without poppler the score drops ~0.013; two PDF pairs escalate instead of
  being compared. The container installs `poppler-utils`.
