// Drop your real reports.json (from `python3 run_pipeline.py --report reports.json`)
// into this folder, next to this file: src/data/reports.json
// It's gitignored at the repo root already, don't fight that, just keep a
// local copy here for dev.
import reports from "./reports.json";

const USE_LIVE_API = false; // flip this once X's endpoints are deployed

export async function getAllEmails() {
  if (USE_LIVE_API) {
    const res = await fetch("/emails");
    return res.json();
  }
  return Object.entries(reports).map(([email_id, r]) => ({
    email_id,
    category: r.classification.category,
    status: r.status,
  }));
}

export async function getEmail(emailId) {
  if (USE_LIVE_API) {
    const res = await fetch(`/emails/${emailId}`);
    return res.json();
  }
  return reports[emailId] ?? null;
}

export async function getReviewQueue() {
  if (USE_LIVE_API) {
    const res = await fetch("/review-queue");
    return res.json();
  }
  return Object.values(reports).filter((r) => r.status === "NEEDS_REVIEW");
}

export async function submitReview(emailId, decision) {
  // decision: { action: "confirm" | "correct", field, value }
  if (USE_LIVE_API) {
    const res = await fetch(`/review/${emailId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    });
    return res.json();
  }
  // No backend yet: log it so you can see the shape you'll eventually send.
  console.log("submitReview (stub, not persisted):", emailId, decision);
  return { ok: true, stub: true };
}