import { useState, useEffect } from "react";
import { getEmail, submitReview, retryEmailProcess, API_BASE_URL } from "../data/reports";

export default function ReportView({ emailId, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("SI");

  const [fieldToCorrect, setFieldToCorrect] = useState("container_count");
  const [correctedValue, setCorrectedValue] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    getEmail(emailId)
      .then(setData)
      .catch(() => alert("Failed to fetch email details"))
      .finally(() => setLoading(false));
  }, [emailId]);

  async function handleReviewAction(actionType) {
    setIsSubmitting(true);
    try {
      const payload = actionType === "correct" 
        ? { action: "correct", field: fieldToCorrect, value: correctedValue }
        : { action: "confirm" };
        
      await submitReview(emailId, payload);
      
      const updatedData = await getEmail(emailId);
      setData(updatedData);
    } catch (error) {
      alert("Failed to submit review: " + error.message);
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
    <div className="max-w-7xl mx-auto p-6 flex flex-col h-screen">
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
        {/* left panel: Raw Context Viewer */}
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

        {/* right panel: Discrepancy Report & Human Loop */}
        <div className="w-1/2 flex flex-col gap-4">
          
          {isReviewNeeded && (
            <div className="bg-rose-50 border border-rose-200 p-5 rounded-lg shadow-sm">
              <h3 className="text-rose-800 font-bold mb-2">⚠️ Human Intervention Required</h3>
              <p className="text-sm text-rose-700 mb-4 font-medium">
                Reason: <span className="font-bold underline">{data.review_reason ? data.review_reason.replaceAll("_", " ") : "Unknown"}</span>. 
                {hasFieldsToCorrect 
                  ? " Please review the document context on the left and input the missing value below." 
                  : " Please review the attached files. You can confirm this failure or retry the pipeline if the file was replaced."}
              </p>
              
              {hasFieldsToCorrect ? (
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <label className="text-xs font-bold text-rose-800 mb-1.5 block uppercase tracking-wide">Target Field</label>
                    <select 
                      className="w-full border border-rose-300 rounded p-2 text-sm bg-white"
                      value={fieldToCorrect}
                      onChange={(e) => setFieldToCorrect(e.target.value)}
                    >
                      <option value="shipper">Shipper</option>
                      <option value="consignee">Consignee</option>
                      <option value="notify_party">Notify Party</option>
                      <option value="port_of_loading">Port of Loading</option>
                      <option value="port_of_discharge">Port of Discharge</option>
                      <option value="container_count">Container Count</option>
                      <option value="gross_weight_kg">Gross Weight</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="text-xs font-bold text-rose-800 mb-1.5 block uppercase tracking-wide">Corrected Value</label>
                    <input 
                      type="text" 
                      className="w-full border border-rose-300 rounded p-2 text-sm bg-white"
                      placeholder="Enter correct value..."
                      value={correctedValue}
                      onChange={(e) => setCorrectedValue(e.target.value)}
                    />
                  </div>
                  <button 
                    onClick={() => handleReviewAction("correct")}
                    disabled={isSubmitting || !correctedValue}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-semibold px-4 py-2 rounded text-sm disabled:opacity-50 transition-colors"
                  >
                    {isSubmitting ? "Updating..." : "Confirm & Update"}
                  </button>
                </div>
              ) : (
                <div className="flex gap-3">
                  <button 
                    onClick={() => handleReviewAction("confirm")}
                    disabled={isSubmitting}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-semibold px-4 py-2 rounded text-sm disabled:opacity-50 transition-colors"
                  >
                    {isSubmitting ? "Processing..." : "Confirm Issue"}
                  </button>
                  <button 
                    onClick={handleRetry}
                    disabled={isSubmitting}
                    className="bg-white border border-rose-300 hover:bg-rose-50 text-rose-700 font-semibold px-4 py-2 rounded text-sm disabled:opacity-50 transition-colors"
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