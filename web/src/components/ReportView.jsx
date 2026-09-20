import { useState, useEffect } from "react";
import { getEmail, submitReview, retryEmailProcess, API_BASE_URL } from "../data/reports";

export default function ReportView({ emailId, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("SI");

  // Multi-field Form State for Human Review
  const [corrections, setCorrections] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    getEmail(emailId)
      .then((res) => {
        setData(res);
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

  async function handleBatchCorrection() {
    setIsSubmitting(true);
    try {
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

  if (loading) return <div className="p-8 text-neutral-500 font-medium">Loading {emailId}...</div>;
  if (!data) return <div className="p-8 text-rose-500">Data not found.</div>;

  const isReviewNeeded = data.status === "NEEDS_REVIEW";
  const hasFieldsToCorrect = data.review_reason === "unreadable" || data.review_reason === "missing_value";

  return (
    <div className="w-full flex flex-col">
      {/* Header Bar */}
      <div className="flex justify-between items-center mb-6">
        <button onClick={onBack} className="text-blue-600 text-sm font-semibold hover:underline flex items-center gap-1.5 cursor-pointer">
          ← Back to Inbox
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-extrabold text-neutral-900">{emailId}</h1>
          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${isReviewNeeded ? 'bg-rose-50 text-rose-700 border-rose-200' : data.status === 'MISMATCH' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
            {data.status.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Full-width 50/50 Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start w-full">
        
        {/* LEFT COLUMN: Raw Document Context Viewer (6 cols) */}
        <div className="lg:col-span-6 flex flex-col border border-neutral-200 rounded-xl bg-white overflow-hidden shadow-xs h-[820px]">
          <div className="flex border-b border-neutral-200 bg-neutral-50">
            {["SI", "BL"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-3 text-sm font-bold transition-colors cursor-pointer ${
                  activeTab === tab ? "border-b-2 border-blue-600 text-blue-700 bg-white" : "text-neutral-500 hover:bg-neutral-100"
                }`}
              >
                Raw Document: {tab}
              </button>
            ))}
          </div>
          <div className="p-6 overflow-y-auto text-sm font-mono text-neutral-700 bg-neutral-50/50 flex-1 space-y-4">
            <p className="text-xs text-neutral-400 font-sans uppercase tracking-wider font-bold">
              Document Path: {data[activeTab.toLowerCase()]?.path || "N/A"}
            </p>
            
            {data.comparisons?.length > 0 ? (
              data.comparisons.map((comp) => (
                 <div key={comp.field} className="p-3 bg-white border border-neutral-200 rounded-lg shadow-2xs">
                   <span className="text-xs font-bold text-blue-600 font-sans uppercase">[{comp.field}]</span>
                   <p className="mt-1 text-neutral-800 whitespace-pre-wrap">{comp[activeTab.toLowerCase()]?.source?.snippet || "Not extracted"}</p>
                 </div>
              ))
            ) : (
              <div className="p-6 bg-blue-50 border border-blue-200 rounded-xl text-blue-900 text-sm font-sans">
                <p className="mb-3 font-bold">No snippets extracted. The system aborted comparison.</p>
                {data[activeTab.toLowerCase()]?.path && (
                  <a 
                    href={`${API_BASE_URL}/${data[activeTab.toLowerCase()].path}`}
                    target="_blank" 
                    rel="noreferrer"
                    className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-2.5 rounded-lg transition-colors shadow-sm"
                  >
                    Open Original File
                  </a>
                )}
              </div>
            )}

            {data[activeTab.toLowerCase()]?.readable === false && (
               <p className="text-rose-600 font-sans font-bold mt-4 p-4 bg-rose-50 border border-rose-200 rounded-lg">
                 ⚠️ Document is unreadable or unsupported format. Please review original attachment manually.
               </p>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Unified Verification & Action Workspace (6 cols) */}
        <div className="lg:col-span-6 flex flex-col gap-6 w-full">
          
          {/* Status Alert Banner */}
          {isReviewNeeded && (
            <div className="bg-rose-50 border border-rose-200 p-5 rounded-xl shadow-xs">
              <h3 className="text-rose-900 font-extrabold text-sm mb-1 flex items-center gap-2">
                <span>⚠️</span> Human Intervention Required: <span className="underline uppercase">{data.review_reason ? data.review_reason.replaceAll("_", " ") : "Unknown"}</span>
              </h3>
              <p className="text-xs text-rose-800 font-medium">
                {hasFieldsToCorrect 
                  ? "Verify reference values against the left viewer, adjust fields in the audit list below, and submit all changes at once." 
                  : "Review the source files. You can confirm this failure or retry processing."}
              </p>
              
              {!hasFieldsToCorrect && (
                <div className="flex gap-3 mt-4">
                  <button 
                    onClick={handleConfirmIssue}
                    disabled={isSubmitting}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-bold px-4 py-2 rounded-lg text-xs disabled:opacity-50 transition-colors shadow-sm cursor-pointer"
                  >
                    {isSubmitting ? "Processing..." : "Confirm Issue"}
                  </button>
                  <button 
                    onClick={handleRetry}
                    disabled={isSubmitting}
                    className="bg-white border border-rose-300 hover:bg-rose-100 text-rose-800 font-bold px-4 py-2 rounded-lg text-xs transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isSubmitting ? "Retrying..." : "Retry Pipeline"}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Unified Comparison & Inline Correction Workspace */}
          <div className="border border-neutral-200 rounded-xl bg-white p-6 shadow-xs flex flex-col h-[740px] w-full">
            <div className="flex justify-between items-center mb-4 border-b border-neutral-100 pb-3">
              <div>
                <h2 className="text-base font-extrabold text-neutral-900">Document Comparison & Audit Workspace</h2>
                <p className="text-xs text-neutral-500">Compare reference SI values with target BL data. Editable fields allow direct overrides.</p>
              </div>
              <span className="text-xs font-bold text-neutral-500 bg-neutral-100 px-2.5 py-1 rounded-md">
                {data.comparisons?.length || 0} Fields Checked
              </span>
            </div>

            {/* Scrollable Field List */}
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {data.comparisons?.length === 0 ? (
                 <p className="text-sm text-neutral-500">No field data available to compare.</p>
              ) : (
                data.comparisons?.map((field) => {
                  const isMismatched = field.status !== 'match';
                  return (
                    <div 
                      key={field.field} 
                      className={`p-4 rounded-xl border transition-all ${
                        isMismatched ? 'border-amber-200 bg-amber-50/30' : 'border-neutral-200 bg-neutral-50/50'
                      }`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <p className="text-xs font-extrabold text-neutral-700 uppercase tracking-wider">{field.field.replace(/_/g, " ")}</p>
                        {isMismatched && (
                          <span className="text-[10px] bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full font-extrabold uppercase tracking-wider">
                            Mismatch
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm mt-2 pt-2 border-t border-neutral-200/60">
                        {/* SI Reference (Read-only) */}
                        <div>
                          <span className="text-neutral-400 text-[10px] font-bold uppercase tracking-wider block mb-1">SI (Reference)</span>
                          <span className="font-semibold text-neutral-900 block truncate">{field.si?.raw || field.si?.value || "—"}</span>
                        </div>

                        {/* BL Target / Editable Input */}
                        <div>
                          <span className="text-neutral-400 text-[10px] font-bold uppercase tracking-wider block mb-1">BL (Target Value)</span>
                          {hasFieldsToCorrect && corrections[field.field] !== undefined ? (
                            <input 
                              type="text" 
                              className="w-full border border-neutral-300 rounded-lg px-3 py-1.5 text-sm bg-white font-bold text-neutral-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all shadow-2xs"
                              value={corrections[field.field]}
                              onChange={(e) => setCorrections({ ...corrections, [field.field]: e.target.value })}
                            />
                          ) : (
                            <span className={`font-semibold block truncate ${isMismatched ? "text-amber-800 font-bold" : "text-neutral-900"}`}>
                              {field.bl?.raw || field.bl?.value || "—"}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Sticky Action Footer for Corrections */}
            {hasFieldsToCorrect && (
              <div className="mt-4 pt-4 border-t border-neutral-200 bg-white">
                <button 
                  onClick={handleBatchCorrection}
                  disabled={isSubmitting}
                  className="w-full bg-rose-600 hover:bg-rose-700 text-white font-bold px-4 py-3 rounded-xl text-sm disabled:opacity-50 transition-colors shadow-sm cursor-pointer"
                >
                  {isSubmitting ? "Submitting All Changes..." : "Confirm & Save All Corrections"}
                </button>
              </div>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}