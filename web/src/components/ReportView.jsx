import { useEffect, useState } from "react";
import { getEmail } from "../data/reports";
import AmendmentDraft from "./AmendmentDraft";

export default function ReportView({ emailId, onBack }) {
  const [result, setResult] = useState(null);

  useEffect(() => {
    setResult(null);
    if (emailId) getEmail(emailId).then(setResult);
  }, [emailId]);

  if (!emailId) {
    return <div className="p-6 text-sm text-neutral-500">No email selected.</div>;
  }
  if (!result) {
    return <div className="p-6 text-sm text-neutral-500">Loading {emailId}...</div>;
  }

  const {
    email_id,
    classification,
    status,
    comparisons,
    notes,
    unconfirmed_mismatches,
  } = result;

  const statusStyles = {
    OK: "bg-emerald-50 text-emerald-700 border-emerald-200",
    MISMATCH: "bg-amber-50 text-amber-800 border-amber-200",
    NEEDS_REVIEW: "bg-rose-50 text-rose-700 border-rose-200",
  };

  const isComparison = classification.category === "BL_COMPARISON";

  // The brief asks for the exact phrase "No mismatch detected" when all seven
  // fields match. It must NOT appear on an email that was never compared -
  // that would claim a check happened when it did not.
  const statusLabel =
    status === "OK"
      ? isComparison
        ? "No mismatch detected"
        : "No comparison needed"
      : status.replaceAll("_", " ");

  // Why there is no comparison table, in the email's own terms.
  const emptyReason = !isComparison
    ? "Not a document-comparison request, so no documents were compared."
    : status === "NEEDS_REVIEW"
    ? "Comparison could not be completed - see the reason above."
    : "No fields were compared.";

  return (
    <div className="max-w-3xl mx-auto p-6">
      <button onClick={onBack} className="text-sm text-neutral-500 hover:text-neutral-800 mb-4">
        ← Back to inbox
      </button>

      <header className="flex items-start justify-between border-b border-neutral-200 pb-4 mb-6">
        <div>
          <p className="text-xs text-neutral-500 tracking-wide">{email_id}</p>
          <h1 className="text-lg font-semibold text-neutral-900 mt-1">
            {classification.category.replaceAll("_", " ")}
          </h1>
          <p className="text-xs text-neutral-400 mt-1">
            classified with {Math.round(classification.confidence * 100)}% confidence
            {" · "}
            {classification.method === "llm" ? "AI fallback" : "rule"}
            {classification.evidence ? ` · matched "${classification.evidence}"` : ""}
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium border whitespace-nowrap ${
            statusStyles[status] ?? "bg-neutral-50 text-neutral-600 border-neutral-200"
          }`}
        >
          {statusLabel}
        </span>
      </header>

      {notes?.length > 0 && (
        <p className="text-sm text-neutral-600 mb-6">{notes.join(" ")}</p>
      )}

      {/* Fields that differ but sit behind an escalation. The system has not
          stood behind these, so they must not look like confirmed findings. */}
      {unconfirmed_mismatches?.length > 0 && (
        <p className="text-sm text-neutral-500 mb-6 border-l-2 border-neutral-300 pl-3">
          {unconfirmed_mismatches.map((f) => f.replaceAll("_", " ")).join(", ")}
          {unconfirmed_mismatches.length === 1 ? " differs" : " differ"} between the
          documents, but this could not be verified - a reviewer should confirm.
        </p>
      )}

      <div className="space-y-1">
        {comparisons?.map((c) => (
          <FieldRow key={c.field} comparison={c} />
        ))}
        {(!comparisons || comparisons.length === 0) && (
          <p className="text-sm text-neutral-400 italic">{emptyReason}</p>
        )}
      </div>

      {status === "MISMATCH" && <AmendmentDraft emailId={email_id} />}
    </div>
  );
}

function FieldRow({ comparison }) {
  const { field, status, si, bl, reason } = comparison;
  const [expanded, setExpanded] = useState(status === "mismatch");
  const isMismatch = status === "mismatch";
  const isUncertain = status === "uncertain";

  return (
    <div
      className={`border rounded-lg px-4 py-3 ${
        isMismatch
          ? "border-amber-200 bg-amber-50/40"
          : isUncertain
          ? "border-neutral-300 bg-neutral-50"
          : "border-neutral-100"
      }`}
    >
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-between text-left"
      >
        <span className="text-sm font-medium text-neutral-800">
          {field.replaceAll("_", " ")}
        </span>
        {isMismatch && <span className="text-xs font-medium text-amber-700">mismatch</span>}
        {isUncertain && <span className="text-xs font-medium text-neutral-500">uncertain</span>}
      </button>

      <div className="grid grid-cols-2 gap-4 mt-2">
        <ValueCell label="SI" field={si} highlight={isMismatch} expanded={expanded} />
        <ValueCell label="BL" field={bl} highlight={isMismatch} expanded={expanded} />
      </div>

      {isUncertain && reason && (
        <p className="text-xs text-neutral-500 mt-2">{reason}</p>
      )}
    </div>
  );
}

function ValueCell({ label, field, highlight, expanded }) {
  if (field?.value == null) {
    return <div className="text-sm text-neutral-400 italic">{label}: not found</div>;
  }

  return (
    <div>
      <p className={`text-sm ${highlight ? "text-amber-900 font-medium" : "text-neutral-700"}`}>
        {field.raw ?? field.value}
      </p>
      {expanded && field.source?.file && (
        <p className="text-xs text-neutral-400 mt-1">
          from {field.source.file.split("/").pop()} line {field.source.line} [
          {field.source.label_seen}]
          {field.confidence ? ` · ${field.confidence.toFixed(2)}` : ""}
          {field.method ? ` · ${field.method}` : ""}
        </p>
      )}
    </div>
  );
}
