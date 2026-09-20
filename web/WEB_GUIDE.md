# Shipping Document Verification — Web Guide

This guide covers the local React frontend connected to the deployed FastAPI backend, following the frontend integration changes. Save this file as `web/WEB_GUIDE.md` in the project if desired.

## 1. How the application works

| Component | Location | Purpose |
| --- | --- | --- |
| React/Vite frontend | Your laptop, usually `http://localhost:5173` | Displays the inbox, reports and review queue |
| FastAPI backend | `https://sdoc-api-856612571283.asia-southeast1.run.app` | Processes sample emails and handles API requests |
| SQLite database | Inside each running backend instance | Stores results and human review decisions temporarily |

The browser fetches results from the live API. You do not need to start a local Python backend for this setup. Opening or refreshing the frontend retrieves saved results; it does not process the emails again.

The application currently uses 520 bundled sample emails and their attachments. It does not connect to your personal mailbox or provide an upload interface.

## 2. First-time frontend setup

Prerequisites: Node.js and npm installed, and the project available on your computer. Check installation in PowerShell:

```powershell
node --version
npm --version
```

The frontend must use the updated `web/src/data/reports.js` API loader, rather than importing a local `reports.json`. That loader must read the `emails` array from `/emails`, the `items` array from `/review-queue`, and translate review `value` into `corrected_value`.

Create `web/.env.local`, alongside `web/package.json` and the `web/src` folder:

```env
VITE_API_BASE_URL=https://sdoc-api-856612571283.asia-southeast1.run.app
```

Do not put Gemini API keys or other secrets into frontend environment variables. This file only needs the public backend URL.

From the project root (`SleeplessMonashians`), run:

```powershell
cd web
npm ci
npm run dev
```

Open the URL printed in the terminal, usually `http://localhost:5173`. Leave this terminal running. If port 5173 is busy, use the alternate URL Vite prints.

Restart the dev server after changing `.env.local`: press Ctrl+C, then run `npm run dev` again. Normal React source edits usually appear automatically.

## 3. Check the backend and load sample data

Open a second PowerShell terminal using the + button in VS Code, or use Windows PowerShell. These HTTP commands work from any directory. Keep the frontend terminal running.

```powershell
$api = "https://sdoc-api-856612571283.asia-southeast1.run.app"
Invoke-RestMethod "$api/health" | ConvertTo-Json -Depth 4
Invoke-RestMethod "$api/stats"
```

The verified deployment reported version `1.1.0`, a Cloud Run revision, and `true` for `llm_enabled`, `llm_cache_present` and `poppler_enabled`. Revision names change on redeployment. These flags indicate availability, not proof that every model request will succeed.

If `processed` is 0, initialise the sample data:

**Warning: `/process` reprocesses the entire sample inbox and overwrites stored reports, including review changes in those reports. Coordinate with teammates and run it before reviewing cases, not during a review demo.**

```powershell
Invoke-RestMethod -Method Post "$api/process" -TimeoutSec 300
```

Wait for completion. The previously verified baseline was:

| Result | Count |
| --- | ---: |
| Processed emails | 520 |
| OK | 455 |
| MISMATCH | 46 |
| NEEDS_REVIEW | 19 |

Check that the backend returns records:

```powershell
(Invoke-RestMethod "$api/emails").count
```

Expected baseline: 520. Refresh the website to display them. No files are imported into localhost; the frontend fetches the backend's results.

## 4. What processing does

1. Classifies each email into `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL` or `SPAM`.
2. Uses rules first and Gemini fallback for uncertain classifications. Cached Gemini answers can be reused without a new model call. Live calls for uncached inputs require a configured backend API key.
3. For comparison requests, reads the Shipping Instruction (SI) and draft Bill of Lading (BL).
4. Extracts and normalises fields such as shipper, consignee, ports, container count and gross weight.
5. Compares the draft BL against the SI reference, assigns a status, and saves the report.

Poppler extracts text from PDFs while preserving layout. It is not OCR; image-only scans can still require review. The current API's Gemini integration assists classification; document comparison is primarily rule-based.

## 5. Using the interface

### Inbox

Use the first dropdown to filter by email category and the second to filter by status. Set both to All to see the full inbox. Click an email to open its report.

| Status | Meaning |
| --- | --- |
| `OK` | No mismatch or unresolved review issue was flagged by the current workflow. This also applies to emails that do not require document comparison. |
| `MISMATCH` | A discrepancy was detected between the SI and draft BL. |
| `NEEDS_REVIEW` | The system could not complete a confident comparison, for example because an attachment or field is missing, unreadable or uncertain. |

Always interpret status together with category. An invoice query marked `OK` does not mean its shipping documents were compared.

### Report

Review the SI and BL field values side by side. Expand a field to inspect available source information. In the baseline dataset, `email_013` demonstrates a port-of-discharge mismatch. The current interface shows extracted values and paths; it does not provide an original attachment viewer.

### Review Queue

Open Review Queue and expand a case to see its reason and available details.

- **Confirm:** saves a human confirmation and marks the case `OK`.
- **Correct:** select a field, enter a value, then click Save correction. The backend records the supplied correction and marks the case `OK`.
- Failed saves should display a red error and leave the case pending with the updated ReviewQueue component.
- Successfully saved cases appear under Resolved this session. That section is local UI state and resets when the component is reopened or the page is refreshed.

The current review implementation does not modify original attachments or recompute comparisons. Marking a case `OK` is a recorded human decision, not a fresh automated verification. Other extracted fields and comparison flags may still reflect the original report.

## 6. Suggested manual test

Start from a freshly processed baseline only if resetting stored report decisions is acceptable.

| Test | Action | Expected baseline result |
| --- | --- | --- |
| Load inbox | Set both filters to All | 520 emails |
| Filter mismatches | Select MISMATCH | 46 emails |
| Inspect report | Open email_013 | Port-of-discharge discrepancy and source details |
| Load review queue | Open Review Queue | 19 cases |
| Confirm case | Confirm one pending case | Saved case leaves the pending queue |
| Correct case | Supply a field correction for another case | Correction saves and case leaves the pending queue |
| Check save | Refresh and check review history | Decision remains if requests reach the same surviving backend instance |

To inspect history, replace the placeholder with the email ID you actually reviewed:

```powershell
$emailId = "REPLACE_WITH_REVIEWED_EMAIL_ID"
Invoke-RestMethod "$api/reviews/$emailId" | ConvertTo-Json -Depth 10
```

For an optional benchmark check, run from the project root with Python dependencies installed:

```powershell
python score_api.py --url https://sdoc-api-856612571283.asia-southeast1.run.app --workers 4
```

**This scorer calls `/process`, so it also resets processed reports. Run it before manual review testing.** The previously verified score was `0.9995`, with 46/46 end-to-end detections, 493 rule classifications and 27 LLM classifications. This is performance on the supplied benchmark, not guaranteed accuracy on new documents.

## 7. Troubleshooting

| Problem | What to check |
| --- | --- |
| Inbox displays 0 of 0 | Check `/stats`. If there are no processed results, initialise the dataset as above. |
| API returns 520 but inbox is empty | Open browser F12 → Network, refresh, and inspect the `emails` request. It should reach the Cloud Run URL and return HTTP 200 with an `emails` array. Check Console for errors. |
| Request goes to localhost:5173/emails | Check the updated API loader and `.env.local`; restart Vite. |
| Missing reports.json error | The old data loader is still importing the JSON file. Use the integrated API loader instead. |
| Correction returns HTTP 400 | Ensure the request sends `corrected_value`, not `value`, to the backend. |
| Review queue loads forever when empty | Use the updated component with a separate loading state and error display. |
| Data disappears or differs between requests | SQLite is local to each backend instance. A replaced instance loses its data; multiple instances can have different results. A shared persistent database is the durable fix. |
| npm says package.json is missing | Run npm commands from the `web` folder. |
| Thousands of files appear in Git | Ignore `web/node_modules/`; commit package.json and package-lock.json instead. |

The frontend does not automatically call `/process` when empty. Avoid repeatedly calling it to work around inconsistent instance storage, because it overwrites report decisions.

## 8. Files to commit

Add these entries to the project-root `.gitignore`:

```gitignore
web/node_modules/
web/dist/
web/.env.local
web/.env.*.local
```

Commit intentional source changes, this guide, frontend configuration, `web/package.json`, `web/package-lock.json` and `.gitignore`. Do not commit downloaded dependencies or secret credentials. Teammates create their own `.env.local` using the public URL above.

## 9. Daily startup and stopping

On later runs, from the project root:

```powershell
cd web
npm run dev
```

Run `npm ci` again when you need to install dependencies from an updated lockfile. If emails are missing, check the backend before resetting any data.

Press Ctrl+C in the frontend terminal to stop the local website. This does not stop the deployed backend. The localhost address is for your own computer; sharing the frontend with remote teammates or judges requires frontend hosting, which is not configured by these steps.
