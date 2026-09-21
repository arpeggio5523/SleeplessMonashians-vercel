// web/src/components/AmendmentDraft.jsx
//
// Shown on a MISMATCH report. The discrepancy is already settled by the
// pipeline; this asks the backend to write the email an operator would send
// to have the draft Bill of Lading corrected.
//
// Add to ReportView, under the comparison table:
//     {report.status === "MISMATCH" && (
//       <AmendmentDraft emailId={report.email_id} />
//     )}

import { useState } from "react";
import { getAmendment } from "../data/reports";
import { useToastStore } from "../store/useToastStore";

export default function AmendmentDraft({ emailId }) {
  const [draft, setDraft] = useState(null);
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const showToast = useToastStore((state) => state.showToast);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const d = await getAmendment(emailId);
      setDraft(d);
      setBody(d.body);
    } catch (e) {
      // Surface the real reason. The common one is pointing at a deployed
      // image that predates this endpoint, which returns 404.
      const msg = e?.message || "";
      setError(
        /404|not found/i.test(msg)
          ? "This API does not have the amendment endpoint yet - the deployed image is older than the code. Point VITE_API_BASE_URL at a current backend, or redeploy."
          : /failed to fetch|networkerror/i.test(msg)
          ? "Could not reach the API. Is the backend running?"
          : msg || "Could not draft the request. Try again."
      );
    } finally {
      setLoading(false);
    }
  }

  async function copy() {
    await navigator.clipboard.writeText(`${draft.subject}\n\n${body}`);
    setCopied(true);
    showToast("Amendment email copied to clipboard!");
    setTimeout(() => setCopied(false), 1500);
  }

  if (!draft) {
    return (
      <div className="mt-8 border-t pt-6">
        <button
          onClick={load}
          disabled={loading}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {loading ? "Drafting…" : "Draft amendment request"}
        </button>
        <p className="mt-2 text-sm text-slate-500">
          Writes the email asking the counterparty to correct the draft B/L.
        </p>
        {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="mt-8 border-t pt-6">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="font-medium">Amendment request</h3>
        <span className="text-xs text-slate-400">
          {draft.source === "llm" ? "drafted by Gemini" : "template"} · review before sending
        </span>
      </div>

      <div className="mb-2 text-sm">
        <span className="text-slate-500">Subject: </span>
        {draft.subject}
      </div>

      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={14}
        className="w-full rounded border border-slate-300 p-3 font-mono text-sm"
      />

      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={copy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white"
        >
          {copied ? "Copied" : "Copy"}
        </button>
        <button
          onClick={load}
          className="rounded border border-slate-300 px-4 py-2 text-sm"
        >
          Regenerate
        </button>
      </div>
    </div>
  );
}