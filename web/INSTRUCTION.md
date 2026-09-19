# Interface Setup and Run

Frontend for the shipping document verification pipeline: inbox, report view, and review queue. Built with Vite, React, and Tailwind, reading from reports.json.

## Prerequisites

Node.js 18 or newer and npm. Check with node v. Install from nodejs.org or with brew install node on macOS.

A copy of reports.json, the full pipeline output. This is not in the repo. See "Getting reports.json" below.

## First time setup

```
cd web
npm install
```

This installs everything from package lock.json. You should not need to install anything individually.

## Getting reports.json
- Get reports.json from the group or,
- reports.json is gitignored (it is 1.4 MB of dataset output, not source code) so every teammate needs their own local copy. Generate it by running the pipeline:

```
python3 run_pipeline.py --report reports.json
```

Then copy it into place:

```
cp reports.json web/src/data/reports.json
```

If you do not have run_pipeline.py on your current branch, use a git worktree to pull it from the pipeline branch without switching your own:

```
git worktree add ../pipeline_check origin/<pipeline_branch_name>
cd ../pipeline_check
python3 run_pipeline.py --report reports.json
cp reports.json ../SleeplessMonashians/web/src/data/reports.json
cd ../SleeplessMonashians
git worktree remove ../pipeline_check
```

Without this file, the app falls back to a one email placeholder. It will run, but the inbox and review queue will look empty.

## Running the dev server

```
cd web
npm run dev
```

Then open the URL it prints, usually http://localhost:5173.

## Project structure

```
web/
  index.html            entry point, do not edit the script src path
  src/
    main.jsx            React entry
    App.jsx             top level routing (inbox, report, review queue)
    data/
      reports.js         data loader (swap USE_LIVE_API to true once wired)
      reports.json        your local copy, see Getting reports.json
    components/
      Nav.jsx
      InboxView.jsx
      ReportView.jsx
      ReviewQueue.jsx
```

## Known gaps

Confirm and Correct in the review queue update local state only. Nothing is persisted yet, since the live API does not have a review or save endpoint. Refreshing the page resets any resolved cases.

No retry button yet for failed or unreadable cases.

Attachment files (the actual SI and BL documents) are not viewable in the app. Only their paths are shown.

## Troubleshooting

Blank page, no console errors: check web/index.html exists and its script tag points to /src/main.jsx, not /web/src/main.jsx.

Command not found python on macOS: use python3 instead

Inbox or review queue look empty: you are likely still on the placeholder reports.json. See [Getting reports.json](## Getting reports.json) above.
