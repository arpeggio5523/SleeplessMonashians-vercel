// web/src/components/DocumentViewer.jsx
//
// Shows an attachment exactly as the pipeline read it, line by line, with the
// lines each field was extracted from highlighted - like a plagiarism report,
// but for shipping documents. Line numbers match the provenance stored on
// every field, so a highlight points at precisely the text that was compared.

import { useEffect, useRef, useState } from "react";
import { documentFileUrl, getDocument, getEmailSource } from "../data/reports";

const STATUS = {
  mismatch: { row: "bg-amber-100", tag: "bg-amber-500 text-white", label: "mismatch" },
  uncertain: { row: "bg-neutral-200/70", tag: "bg-neutral-500 text-white", label: "uncertain" },
  match: { row: "bg-emerald-50", tag: "bg-emerald-600 text-white", label: "match" },
};

const pretty = (f) => f.replaceAll("_", " ");

// ---------------------------------------------------------------------------
// one document
// ---------------------------------------------------------------------------

export function DocumentPane({ emailId, which, compact = false, focusField = null }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);
  const firstMismatch = useRef(null);
  const focused = useRef(null);

  useEffect(() => {
    setDoc(null);
    setError(null);
    getDocument(emailId, which)
      .then(setDoc)
      .catch((e) => setError(e.message || "Could not load the document."));
  }, [emailId, which]);

  // bring the most important line into view: the focused field if one was
  // chosen, otherwise the first mismatch
  useEffect(() => {
    const target = focused.current || firstMismatch.current;
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [doc, focusField]);

  if (error) {
    return <p className="p-4 text-sm text-neutral-500 italic font-sans">{error}</p>;
  }
  if (!doc) {
    return <p className="p-4 text-sm text-neutral-400 font-sans">Loading {which.toUpperCase()}…</p>;
  }

  // line number -> highlights on that line (a line can carry several fields)
  const byLine = {};
  for (const h of doc.highlights) (byLine[h.line] ||= []).push(h);
  const firstMismatchLine = doc.highlights.find((h) => h.status === "mismatch")?.line;

  const header = (
    <div className="flex items-center justify-between gap-3 px-3 py-2 border-b border-neutral-200 bg-neutral-50 font-sans">
      <div className="min-w-0">
        <span className="text-xs font-bold text-neutral-800">{which.toUpperCase()}</span>
        <span className="ml-2 text-[11px] text-neutral-400 truncate">
          {doc.path.split("/").pop()} · read as {doc.ingest_method}
        </span>
      </div>
      <a
        href={documentFileUrl(emailId, which)}
        target="_blank"
        rel="noreferrer"
        className="shrink-0 text-[11px] font-bold text-blue-600 hover:underline"
      >
        Open original
      </a>
    </div>
  );

  if (!doc.readable) {
    return (
      <div className="flex flex-col h-full">
        {header}
        <div className="p-4 text-sm font-sans text-rose-700 bg-rose-50">
          No text could be recovered from this file.
          {doc.warnings?.length > 0 && (
            <span className="block mt-1 text-xs text-rose-500">{doc.warnings.at(-1)}</span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {header}

      {doc.ingest_method === "ocr" && (
        <p className="px-3 py-2 text-[11px] font-sans font-bold text-amber-800 bg-amber-50 border-b border-amber-200">
          Scanned page - this is OCR text. Check values against the original.
        </p>
      )}

      <div className="overflow-auto flex-1 min-h-0 bg-white">
        <table className="w-full border-collapse font-mono text-[12px] leading-5">
          <tbody>
            {doc.lines.map((text, i) => {
              const n = i + 1;
              const hs = byLine[n] || [];
              // strongest status on the line decides its colour
              const status = hs.some((h) => h.status === "mismatch")
                ? "mismatch"
                : hs.some((h) => h.status === "uncertain")
                ? "uncertain"
                : hs.length
                ? "match"
                : null;
              const isFocus = focusField && hs.some((h) => h.field === focusField);
              return (
                <tr
                  key={n}
                  ref={(el) => {
                    if (n === firstMismatchLine) firstMismatch.current = el;
                    if (isFocus) focused.current = el;
                  }}
                  className={`${status ? STATUS[status].row : ""} ${isFocus ? "outline outline-2 outline-blue-500" : ""}`}
                >
                  <td className="select-none text-right pr-3 pl-2 text-neutral-300 align-top w-10">{n}</td>
                  <td className="pr-3 whitespace-pre align-top text-neutral-800">
                    {text || " "}
                  </td>
                  {!compact && (
                    <td className="pr-2 align-top text-right whitespace-nowrap">
                      {hs.map((h) => (
                        <span
                          key={h.field}
                          title={`matched label: ${h.label}`}
                          className={`ml-1 inline-block rounded px-1.5 text-[10px] font-sans font-bold ${STATUS[h.status].tag}`}
                        >
                          {pretty(h.field)}
                        </span>
                      ))}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// the email itself
// ---------------------------------------------------------------------------

export function EmailPane({ emailId }) {
  const [email, setEmail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setEmail(null);
    setError(null);
    getEmailSource(emailId).then(setEmail).catch((e) => setError(e.message));
  }, [emailId]);

  if (error) return <p className="p-4 text-sm text-neutral-500 italic font-sans">{error}</p>;
  if (!email) return <p className="p-4 text-sm text-neutral-400 font-sans">Loading email…</p>;

  const row = (k, v) =>
    v ? (
      <div className="flex gap-3 text-sm">
        <span className="w-16 shrink-0 text-neutral-400">{k}</span>
        <span className="text-neutral-800 break-words min-w-0">{v}</span>
      </div>
    ) : null;

  return (
    <div className="p-4 font-sans space-y-1.5 overflow-auto h-full">
      {row("From", email.from)}
      {row("To", email.to)}
      {row("Date", email.date)}
      {row("Subject", email.subject)}
      {email.attachments?.length > 0 &&
        row("Attached", email.attachments.map((a) => a.split("/").pop()).join(", "))}
      <pre className="mt-4 pt-4 border-t border-neutral-200 whitespace-pre-wrap text-sm text-neutral-800 font-sans">
        {email.body}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SI and BL side by side
// ---------------------------------------------------------------------------

export function SideBySide({ emailId, focusField }) {
  return (
    <div className="border border-neutral-200 rounded-xl bg-white overflow-hidden shadow-xs">
      <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-200">
        <h3 className="text-sm font-bold text-neutral-900">Source documents</h3>
        <div className="flex gap-3 text-[11px] font-sans text-neutral-500">
          <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-300 mr-1 align-middle" />mismatch</span>
          <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-neutral-300 mr-1 align-middle" />uncertain</span>
          <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-200 mr-1 align-middle" />match</span>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-neutral-200 h-[560px]">
        <DocumentPane emailId={emailId} which="si" focusField={focusField} />
        <DocumentPane emailId={emailId} which="bl" focusField={focusField} />
      </div>
    </div>
  );
}
