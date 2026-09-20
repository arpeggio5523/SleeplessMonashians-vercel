import { useEffect, useMemo, useState } from "react";
import { getAllEmails } from "../data/reports";

const statusColor = {
  OK: "text-emerald-700 bg-emerald-50",
  MISMATCH: "text-amber-700 bg-amber-50",
  NEEDS_REVIEW: "text-rose-700 bg-rose-50",
};

export default function InboxView({ onSelect }) {
  const [emails, setEmails] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    getAllEmails().then(setEmails);
  }, []);

  const categories = useMemo(
    () => ["ALL", ...new Set(emails.map((e) => e.category))],
    [emails]
  );
  const statuses = useMemo(
    () => ["ALL", ...new Set(emails.map((e) => e.status))],
    [emails]
  );

  const filtered = emails.filter(
    (e) =>
      (categoryFilter === "ALL" || e.category === categoryFilter) &&
      (statusFilter === "ALL" || e.status === statusFilter)
  );

  const summary = {
    total: emails.length,
    ok: emails.filter(e => e.status === "OK").length,
    mismatch: emails.filter(e => e.status === "MISMATCH").length,
    review: emails.filter(e => e.status === "NEEDS_REVIEW").length,
  };

  return (
    <div className="max-w-5xl mx-auto p-6">

      {/* Execution control panel */}
      <div className="bg-white p-5 mb-6 border border-neutral-200 rounded-lg shadow-sm">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-base font-bold text-neutral-800">Pipeline Validation Results</h2>
          <span className="bg-blue-100 text-blue-800 text-xs font-bold px-2 py-1 rounded">AI Fallback: ON</span>
        </div>
        
        <table className="w-full text-sm text-left text-neutral-600 border-collapse">
          <thead className="text-xs text-neutral-500 uppercase bg-neutral-50 border-b border-neutral-200">
            <tr>
              <th className="px-4 py-2">Dataset</th>
              <th className="px-4 py-2">Rules</th>
              <th className="px-4 py-2">+ Gemini</th>
              <th className="px-4 py-2">End-to-End</th>
              <th className="px-4 py-2">Defect P/R</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-neutral-100">
              <td className="px-4 py-2 font-medium text-neutral-800">Supplied (Seed 42)</td>
              <td className="px-4 py-2">0.9904</td>
              <td className="px-4 py-2">0.9995</td>
              <td className="px-4 py-2">1.0000</td>
              <td className="px-4 py-2">1.000 / 1.000</td>
            </tr>
            <tr>
              <td className="px-4 py-2 font-medium text-neutral-800">5 Unseen Seeds</td>
              <td className="px-4 py-2">—</td>
              <td className="px-4 py-2 font-bold text-blue-600">0.9990 ± 0.0011</td>
              <td className="px-4 py-2">1.0000</td>
              <td className="px-4 py-2">1.000 / 1.000</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Summary dashboard */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 border border-neutral-200 rounded-lg shadow-sm">
          <p className="text-xs text-neutral-500 font-semibold uppercase">Total Emails</p>
          <p className="text-2xl font-bold text-neutral-800">{summary.total}</p>
        </div>
        <div className="bg-emerald-50 p-4 border border-emerald-200 rounded-lg shadow-sm">
          <p className="text-xs text-emerald-700 font-semibold uppercase">Clean (OK)</p>
          <p className="text-2xl font-bold text-emerald-800">{summary.ok}</p>
        </div>
        <div className="bg-amber-50 p-4 border border-amber-200 rounded-lg shadow-sm">
          <p className="text-xs text-amber-700 font-semibold uppercase">Mismatches</p>
          <p className="text-2xl font-bold text-amber-800">{summary.mismatch}</p>
        </div>
        <div className="bg-rose-50 p-4 border border-rose-200 rounded-lg shadow-sm">
          <p className="text-xs text-rose-700 font-semibold uppercase">Needs Review</p>
          <p className="text-2xl font-bold text-rose-800">{summary.review}</p>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-3 mb-4 items-center">
        <Select value={categoryFilter} onChange={setCategoryFilter} options={categories} />
        <Select value={statusFilter} onChange={setStatusFilter} options={statuses} />
        <span className="text-sm text-neutral-500 self-center ml-auto">
          Showing {filtered.length} of {emails.length}
        </span>
      </div>

      {/* Email list */}
      <div className="border border-neutral-200 rounded-lg divide-y divide-neutral-100 bg-white overflow-hidden">
        {filtered.map((e) => (
          <button
            key={e.email_id}
            onClick={() => onSelect(e.email_id)}
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-neutral-50"
          >
            <div>
              <p className="text-sm font-medium text-neutral-800">{e.email_id}</p>
              <p className="text-xs text-neutral-500">{e.category.replaceAll("_", " ")}</p>
            </div>
            <span
              className={`text-xs font-medium px-2 py-1 rounded ${
                statusColor[e.status] ?? "text-neutral-600 bg-neutral-100"
              }`}
            >
              {e.status.replace("_", " ")}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={(ev) => onChange(ev.target.value)}
      className="text-sm border border-neutral-200 rounded-md px-2 py-1.5 bg-white"
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o === "ALL" ? "All" : o.replaceAll("_", " ")}
        </option>
      ))}
    </select>
  );
}
