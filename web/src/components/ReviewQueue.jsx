import { useEffect, useState } from "react";
import { getReviewQueue, submitReview } from "../data/reports.js";

const reasonCopy = {
  missing_attachment: "A comparison was asked for, but the documents weren't attached.",
  unreadable: "Attachment present, but no text could be recovered (likely a scanned image).",
  wrong_doc_type: "Not an SI/BL pair, an invoice or packing list was sent instead.",
  missing_value: "A required field is blank or a placeholder (TBA, ____MT).",
  low_confidence: "Extracted, but not confidently enough to judge a match or mismatch.",
};

const FIELD_LABELS = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify Party",
  port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge",
  container_count: "Container Count",
  gross_weight_kg: "Gross Weight (kg)",
};

export default function ReviewQueue() {
  const [queue, setQueue] = useState([]);
  const [resolved, setResolved] = useState({}); // email_id -> { action, field?, value? }
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    getReviewQueue().then(setQueue);
  }, []);

  async function handleConfirm(emailId) {
    await submitReview(emailId, { action: "confirm" });
    setResolved((prev) => ({ ...prev, [emailId]: { action: "confirm" } }));
  }

  async function handleCorrect(emailId, field, value) {
    await submitReview(emailId, { action: "correct", field, value });
    setResolved((prev) => ({ ...prev, [emailId]: { action: "correct", field, value } }));
    setExpandedId(null);
  }

  const pending = queue.filter((e) => !resolved[e.email_id]);
  const done = queue.filter((e) => resolved[e.email_id]);

  if (queue.length === 0) {
    return <div className="max-w-3xl mx-auto p-6 text-sm text-neutral-500">Loading queue...</div>;
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <p className="text-sm text-neutral-500 mb-4">
        {pending.length} case{pending.length === 1 ? "" : "s"} awaiting review
        {done.length > 0 && <span className="text-emerald-600"> · {done.length} resolved this session</span>}
      </p>

      <div className="space-y-3">
        {pending.map((e) => (
          <ReviewCard
            key={e.email_id}
            email={e}
            expanded={expandedId === e.email_id}
            onToggle={() => setExpandedId(expandedId === e.email_id ? null : e.email_id)}
            onConfirm={() => handleConfirm(e.email_id)}
            onCorrect={(field, value) => handleCorrect(e.email_id, field, value)}
          />
        ))}
        {pending.length === 0 && (
          <p className="text-sm text-neutral-400 italic">Queue clear.</p>
        )}
      </div>

      {done.length > 0 && (
        <div className="mt-8">
          <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide mb-2">
            Resolved this session
          </p>
          <div className="space-y-1">
            {done.map((e) => {
              const r = resolved[e.email_id];
              return (
                <div key={e.email_id} className="text-xs text-neutral-400 px-3 py-1.5">
                  {e.email_id} — {r.action === "confirm" ? "confirmed" : `corrected ${FIELD_LABELS[r.field] ?? r.field}`}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewCard({ email, expanded, onToggle, onConfirm, onCorrect }) {
  const { email_id, review_reason, si, bl, notes, comparisons } = email;
  const [field, setField] = useState("");
  const [value, setValue] = useState("");
  const [showCorrectForm, setShowCorrectForm] = useState(false);

  const availableFields = Object.keys(FIELD_LABELS);

  function submitCorrect(e) {
    e.preventDefault();
    if (!field || !value.trim()) return;
    onCorrect(field, value.trim());
  }

  return (
    <div className="border border-rose-200 bg-rose-50/40 rounded-lg overflow-hidden">
      <button onClick={onToggle} className="w-full text-left px-4 py-3 flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-800">{email_id}</p>
          <p className="text-xs font-medium text-rose-700 mt-0.5">
            {review_reason?.replaceAll("_", " ") ?? "needs review"}
          </p>
        </div>
        <span className="text-xs text-neutral-400 mt-1">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-rose-200/60 pt-3">
          <p className="text-sm text-neutral-600 mb-3">
            {reasonCopy[review_reason] ?? "This case could not be resolved automatically."}
          </p>

          {notes?.length > 0 && (
            <p className="text-xs text-neutral-500 mb-3">{notes.join(" ")}</p>
          )}

          {(si?.path || bl?.path) && (
            <div className="text-xs text-neutral-400 mb-3 space-y-0.5">
              {si?.path && (
                <p>SI: {si.path} {si.readable === false ? "(unreadable)" : ""}</p>
              )}
              {bl?.path && (
                <p>BL: {bl.path} {bl.readable === false ? "(unreadable)" : ""}</p>
              )}
            </div>
          )}

          {comparisons?.length > 0 && (
            <div className="mb-4 space-y-1.5">
              {comparisons.map((c) => (
                <div key={c.field} className="text-xs bg-white/60 rounded px-2.5 py-1.5 flex justify-between gap-2">
                  <span className="font-medium text-neutral-600">{FIELD_LABELS[c.field] ?? c.field}</span>
                  <span className="text-neutral-500 truncate">
                    SI: {c.si?.raw ?? "—"} · BL: {c.bl?.raw ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {!showCorrectForm ? (
            <div className="flex gap-2">
              <button
                onClick={onConfirm}
                className="text-xs font-medium px-3 py-1.5 rounded-md bg-neutral-900 text-white hover:bg-neutral-800"
              >
                Confirm
              </button>
              <button
                onClick={() => setShowCorrectForm(true)}
                className="text-xs font-medium px-3 py-1.5 rounded-md border border-neutral-300 text-neutral-700 hover:bg-white"
              >
                Correct
              </button>
            </div>
          ) : (
            <form onSubmit={submitCorrect} className="space-y-2">
              <div className="flex gap-2">
                <select
                  value={field}
                  onChange={(e) => setField(e.target.value)}
                  className="text-xs border border-neutral-300 rounded-md px-2 py-1.5 bg-white flex-shrink-0"
                >
                  <option value="">Which field?</option>
                  {availableFields.map((f) => (
                    <option key={f} value={f}>{FIELD_LABELS[f]}</option>
                  ))}
                </select>
                <input
                  type="text"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  placeholder="Correct value"
                  className="text-xs border border-neutral-300 rounded-md px-2 py-1.5 bg-white flex-1"
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={!field || !value.trim()}
                  className="text-xs font-medium px-3 py-1.5 rounded-md bg-neutral-900 text-white hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Save correction
                </button>
                <button
                  type="button"
                  onClick={() => setShowCorrectForm(false)}
                  className="text-xs font-medium px-3 py-1.5 rounded-md text-neutral-500 hover:text-neutral-700"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
