import { useState, useEffect } from "react";
import { getEmail, submitReview, retryEmailProcess, API_BASE_URL } from "../data/reports";

export default function ReportView({ emailId, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("SI");

  const [corrections, setCorrections] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    getEmail(emailId)
      .then((res) => {
        setData(res);
        // Pre-fill the form with existing BL/Target values or empty strings
        if (res.comparisons) {
          const initialValues = {};
          res.comparisons.forEach((comp) => {
            initialValues[comp.field] = comp.bl?.raw || comp.bl?.value || "";
          });
          setCorrections(initialValues);
        }
      })
      .catch(() => alert("Failed to fetch email details"))
      .finally(() => setLoading(false));
  }, [emailId]);

  // Handle batch review submission (loops client-side to submit each edited field)
  async function handleBatchCorrection() {
    setIsSubmitting(true);
    try {
      // Loop through each field modified by the user
      for (const [field, value] of Object.entries(corrections)) {
        await submitReview(emailId, {
          action: "correct",
          field: field,
          value: value,
        });
      }
      
      alert("Successfully submitted all corrections!");
      const updatedData = await getEmail(emailId);
      setData(updatedData);
    } catch (error) {
      alert("Failed to submit corrections: " + error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirmIssue() {
    setIsSubmitting(true);
    try {
      await submitReview(emailId, { action: "confirm" });
      const updatedData = await getEmail(emailId);
      setData(updatedData);
    } catch (error) {
      alert("Failed to confirm issue: " + error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRetry() {
    setIsSubmitting(true);
    try {
      await retryEmailProcess(emailId);
      const updatedData = await getEmail(emailId);
      setData(updatedData);
    } catch (error) {
      alert("Failed to retry pipeline: " + error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loading) return <div className="p-6 text-neutral-500 font-medium">Loading {emailId}...</div>;
  if (!data) return <div className="p-6 text-rose-500">Data not found.</div>;

  const isReviewNeeded = data.status === "NEEDS_REVIEW";
  const hasFieldsToCorrect = data.review_reason === "unreadable" || data.review_reason === "missing_value";

  return (
    <div className="max-w-5xl mx-auto p-6 flex flex-col">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <button onClick={onBack} className="text-blue-600 text-sm font-medium hover:underline">
          ← Back to Inbox
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-neutral-800">{emailId}</h1>
          <span className={`px-2 py-1 rounded text-xs font-bold ${isReviewNeeded ? 'bg-rose-100 text-rose-700' : data.status === 'MISMATCH' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
            {data.status.replace("_", " ")}
          </span>
        </div>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Left panel: Raw Context Viewer */}
        <div className="w-1/2 flex flex-col border border-neutral-200 rounded-lg bg-white overflow-hidden shadow-sm">
          <div className="flex border-b border-neutral-200 bg-neutral-50">
            {["SI", "BL"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2.5 text-sm font-semibold transition-colors ${
                  activeTab === tab ? "border-b-2 border-blue-600 text-blue-700 bg-white" : "text-neutral-500 hover:bg-neutral-100"
                }`}
              >
                Raw Document: {tab}
              </button>
            ))}
          </div>
          <div className="p-4 overflow-y-auto text-sm font-mono text-neutral-700 bg-neutral-50 flex-1">
            <p className="mb-4 text-xs text-neutral-400 font-sans uppercase tracking-wide">
              Document Path: {data[activeTab.toLowerCase()]?.path || "N/A"}
            </p>
            
            {data.comparisons?.length > 0 ? (
              data.comparisons.map((comp) => (
                 <div key={comp.field} className="mb-3">
                   <span className="text-neutral-400">[{comp.field}]</span>
                   <br />
                   {comp[activeTab.toLowerCase()]?.source?.snippet || "Not extracted"}
                 </div>
              ))
            ) : (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-md text-blue-800 text-sm font-sans">
                <p className="mb-3 font-medium">No snippets extracted. The system aborted comparison.</p>
                {data[activeTab.toLowerCase()]?.path && (
                  <a 
                    href={`${API_BASE_URL}/${data[activeTab.toLowerCase()].path}`}
                    target="_blank" 
                    rel="noreferrer"
                    className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold px-4 py-2 rounded transition-colors"
                  >
                    Open Original File
                  </a>
                )}
              </div>
            )}

            {data[activeTab.toLowerCase()]?.readable === false && (
               <p className="text-rose-500 font-sans font-medium mt-4">
                 ⚠️ Document is unreadable or unsupported format. Please review original attachment manually.
               </p>
            )}
          </div>
        </div>

        {/* Right panel: Discrepancy Report & Human Loop */}
        <div className="w-1/2 flex flex-col gap-4">
          
          {isReviewNeeded && (
            <div className="bg-rose-50 border border-rose-200 p-5 rounded-lg shadow-sm">
              <h3 className="text-rose-800 font-bold mb-2">⚠️ Human Intervention Required</h3>
              <p className="text-sm text-rose-700 mb-4 font-medium">
                Reason: <span className="font-bold underline">{data.review_reason ? data.review_reason.replaceAll("_", " ") : "Unknown"}</span>. 
                {hasFieldsToCorrect 
                  ? " Review all fields below, make any necessary adjustments, and submit with a single confirmation." 
                  : " Please review the attached files. You can confirm this failure or retry the pipeline if the file was replaced."}
              </p>
              
              {hasFieldsToCorrect ? (
                <div className="space-y-3">
                  <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
                    {Object.keys(corrections).map((fieldName) => (
                      <div key={fieldName} className="bg-white p-2.5 rounded border border-rose-200">
                        <label className="text-[11px] font-bold text-neutral-600 block uppercase tracking-wide mb-1">
                          {fieldName.replaceAll("_", " ")}
                        </label>
                        <input 
                          type="text" 
                          className="w-full border border-neutral-300 rounded p-1.5 text-sm bg-white font-medium text-neutral-800 focus:border-rose-500 outline-none"
                          value={corrections[fieldName]}
                          onChange={(e) => setCorrections({ ...corrections, [fieldName]: e.target.value })}
                        />
                      </div>
                    ))}
                  </div>
                  <button 
                    onClick={handleBatchCorrection}
                    disabled={isSubmitting}
                    className="w-full bg-rose-600 hover:bg-rose-700 text-white font-semibold px-4 py-2.5 rounded text-sm disabled:opacity-50 transition-colors shadow-sm"
                  >
                    {isSubmitting ? "Submitting All..." : "Confirm All Corrections"}
                  </button>
                </div>
              ) : (
                <div className="flex gap-3">
                  <button 
                    onClick={handleConfirmIssue}
                    disabled={isSubmitting}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-semibold px-4 py-2 rounded text-sm disabled:opacity-50 transition-colors"
                  >
                    {isSubmitting ? "Processing..." : "Confirm Issue"}
                  </button>
                  <button 
                    onClick={handleRetry}
                    disabled={isSubmitting}
                    className="bg-white border border-rose-300 hover:bg-rose-50 text-rose-700 font-semibold px-4 py-2 rounded text-sm transition-colors disabled:opacity-50"
                  >
                    {isSubmitting ? "Retrying..." : "Retry Pipeline"}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 7-Field Comparison Table */}
          <div className="border border-neutral-200 rounded-lg bg-white p-5 overflow-y-auto flex-1 shadow-sm">
            <h2 className="text-base font-bold text-neutral-800 mb-4 border-b pb-2">Comparison Results</h2>
            {data.comparisons?.length === 0 ? (
               <p className="text-sm text-neutral-500">No field data available to compare.</p>
            ) : (
              <div className="space-y-3">
                {data.comparisons?.map((field) => (
                  <div key={field.field} className={`p-3 rounded-md border ${field.status === 'match' ? 'border-neutral-200 bg-neutral-50' : 'border-amber-300 bg-amber-50'}`}>
                    <div className="flex justify-between items-center mb-2">
                      <p className="text-xs font-bold text-neutral-600 uppercase tracking-wide">{field.field.replace(/_/g, " ")}</p>
                      {field.status !== 'match' && <span className="text-[10px] bg-amber-200 text-amber-800 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">Mismatch</span>}
                    </div>
                    <div className="flex justify-between text-sm">
                      <div className="w-1/2 pr-3">
                        <span className="text-neutral-400 text-[10px] font-bold uppercase tracking-wide block mb-1">SI (Reference)</span>
                        <span className="font-medium text-neutral-800">{field.si?.raw || field.si?.value || "—"}</span>
                      </div>
                      <div className="w-1/2 pl-3 border-l border-neutral-300">
                        <span className="text-neutral-400 text-[10px] font-bold uppercase tracking-wide block mb-1">BL (Target)</span>
                        <span className={`font-medium ${field.status !== 'match' ? "text-amber-700 font-bold" : "text-neutral-800"}`}>
                          {field.bl?.raw || field.bl?.value || "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}