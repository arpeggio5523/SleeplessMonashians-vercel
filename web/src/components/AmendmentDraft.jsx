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

  async function load(isRegenerate = false) {
    setLoading(true);
    setError(null);
    try {
      const d = await getAmendment(emailId, isRegenerate);
      setDraft(d);
      setBody(d.body);
    } catch (e) {
      const msg = e?.message || "";
      setError(
        /404|not found/i.test(msg)
          ? "This API does not have the amendment endpoint yet..."
          : msg || "Could not draft the request. Try again."
      );
    } finally {
      setLoading(false);
    }
  }

  async function copy() {
    if (!draft) return;
    await navigator.clipboard.writeText(`${draft.subject}\n\n${body}`);
    setCopied(true);
    showToast("Amendment email copied to clipboard!");
    setTimeout(() => setCopied(false), 1500);
  }

  if (!emailId) return null;

  if (!draft) {
    return (
      <div className="mt-8 border-t pt-6">
        <button
          onClick={load}
          disabled={loading}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50 flex items-center gap-2 cursor-pointer"
        >
          {loading && (
            <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          )}
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
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white cursor-pointer"
        >
          {copied ? "Copied" : "Copy"}
        </button>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="rounded border border-slate-300 px-4 py-2 text-sm flex items-center gap-2 disabled:opacity-50 cursor-pointer"
        >
          {loading && (
            <svg className="animate-spin h-4 w-4 text-slate-700" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          )}
          {loading ? "Regenerating..." : "Regenerate"}
        </button>
      </div>
    </div>
  );
}