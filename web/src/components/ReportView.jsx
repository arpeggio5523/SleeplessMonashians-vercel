import { useEffect, useState } from "react";
import { getEmail, submitReview, retryEmailProcess } from "../data/reports";
import AmendmentDraft from "./AmendmentDraft";
import { DocumentPane, EmailPane, SideBySide } from "./DocumentViewer";
import { useT } from "../i18n";

export default function ReportView({ emailId, onBack }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("EMAIL");
  const [focusField, setFocusField] = useState(null);

  // Multi-field Form State for Human Review
  const [corrections, setCorrections] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setLoading(true);
    getEmail(emailId)
      .then((res) => {
        setData(res);
        setFocusField(null);
        setActiveTab(res.comparisons?.length ? "SI" : "EMAIL");
        if (res.comparisons) {
          const initialValues = {};
          res.comparisons.forEach((comp) => {
            // Prefer the BL's value; if the BL side has nothing (typical when OCR
            // missed a field), offer the SI's as the likeliest intended value.
            initialValues[comp.field] =
              comp.bl?.raw || comp.bl?.value || comp.si?.raw || comp.si?.value || "";
          });
          setCorrections(initialValues);
        }
      })
      .catch(() => alert(t("Failed to fetch email details")))
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
      
      alert(t("Successfully submitted all corrections!"));
      const updatedData = await getEmail(emailId);
      setData(updatedData);
    } catch (error) {
      alert(t("Failed to submit corrections:") + " " + error.message);
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
      alert(t("Failed to confirm issue:") + " " + error.message);
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
      alert(t("Failed to retry pipeline:") + " " + error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  // Prevent destructuring crashes by returning early if loading or no data
  if (loading) return <div className="p-8 text-neutral-500 font-medium">{t("Loading")} {emailId}...</div>;
  if (!data) return <div className="p-8 text-rose-500">{t("Data not found.")}</div>;

  const {
    classification,
    status,
    comparisons,
  } = data;

  const isReviewNeeded = status === "NEEDS_REVIEW";
  const hasComparisons = comparisons && comparisons.length > 0;
  const hasFieldsToCorrect = hasComparisons && (data.review_reason === "unreadable" || data.review_reason === "missing_value");

  const isComparison = classification?.category === "BL_COMPARISON";

  // The brief asks for the exact phrase "No mismatch detected" when all seven fields match. 
  // It must NOT appear on an email that was never compared - that would claim a check happened when it did not.
  const statusLabel =
    status === "OK"
      ? isComparison
        ? t("No mismatch detected")
        : t("No comparison needed")
      : t(status.replaceAll("_", " "));

  return (
    <div className="w-full flex flex-col">
      {/* Header Bar */}
      <div className="flex justify-between items-center mb-6">
        <button onClick={onBack} className="text-blue-600 text-sm font-semibold hover:underline flex items-center gap-1.5 cursor-pointer">
          {t("← Back to Inbox")}
        </button>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-extrabold text-neutral-900">{emailId}</h1>
          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${isReviewNeeded ? 'bg-rose-50 text-rose-700 border-rose-200' : status === 'MISMATCH' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
            {status.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Dynamic Grid Layout */}
      <div className={`grid grid-cols-1 ${hasComparisons ? 'lg:grid-cols-12' : 'lg:grid-cols-1'} gap-8 items-start w-full`}>
        
        {/* LEFT COLUMN: the original email and its attachments, as read */}
        <div className={`flex flex-col border border-neutral-200 rounded-xl bg-white overflow-hidden shadow-xs ${hasComparisons ? 'lg:col-span-6 h-[820px]' : 'w-full h-[560px]'}`}>
          <div className="flex border-b border-neutral-200 bg-neutral-50">
            {(isComparison ? ["EMAIL", "SI", "BL"] : ["EMAIL"]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-3 text-sm font-bold transition-colors cursor-pointer ${
                  activeTab === tab ? "border-b-2 border-blue-600 text-blue-700 bg-white" : "text-neutral-500 hover:bg-neutral-100"
                }`}
              >
                {tab === "EMAIL" ? t("Email") : `${t("Raw Document")}: ${tab}`}
              </button>
            ))}
          </div>
          <div className="flex-1 min-h-0">
            {activeTab === "EMAIL" ? (
              <EmailPane emailId={emailId} />
            ) : (
              <DocumentPane emailId={emailId} which={activeTab.toLowerCase()} focusField={focusField} />
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Unified Verification & Action Workspace */}
        <div className={`${hasComparisons ? 'lg:col-span-6 flex flex-col gap-6 w-full' : 'w-full'}`}>
          
          {status === "MISMATCH" && (
            <div className="border border-neutral-200 rounded-xl bg-white p-6 shadow-xs">
              <AmendmentDraft emailId={emailId} />
            </div>
          )}
        
          {/* Status Alert Banner */}
          {isReviewNeeded && (
            <div className="bg-rose-50 border border-rose-200 p-5 rounded-xl shadow-xs">
              <h3 className="text-rose-900 font-extrabold text-sm mb-1 flex items-center gap-2">
                <span>⚠️</span> {t("Human Intervention Required:")} <span className="underline uppercase">{t(data.review_reason ? data.review_reason.replaceAll("_", " ") : "Unknown")}</span>
              </h3>
              <p className="text-xs text-rose-800 font-medium">
                {hasFieldsToCorrect 
                  ? t("Verify reference values against the left viewer, adjust fields in the audit list below, and submit all changes at once.") 
                  : t("Review the source files. You can confirm this failure or retry processing.")}
              </p>
              
              {!hasFieldsToCorrect && (
                <div className="flex gap-3 mt-4">
                  <button 
                    onClick={handleConfirmIssue}
                    disabled={isSubmitting}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-bold px-4 py-2 rounded-lg text-xs disabled:opacity-50 transition-colors shadow-sm cursor-pointer"
                  >
                    {isSubmitting ? t("Processing...") : t("Confirm Issue")}
                  </button>
                  <button 
                    onClick={handleRetry}
                    disabled={isSubmitting}
                    className="bg-white border border-rose-300 hover:bg-rose-100 text-rose-800 font-bold px-4 py-2 rounded-lg text-xs transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    {isSubmitting ? t("Retrying...") : t("Retry Pipeline")}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Unified Comparison & Inline Correction Workspace */}
          {hasComparisons && (
            <div className="border border-neutral-200 rounded-xl bg-white p-6 shadow-xs flex flex-col h-[740px] w-full">
              <div className="flex justify-between items-center mb-4 border-b border-neutral-100 pb-3">
                <div>
                  <h2 className="text-base font-extrabold text-neutral-900">{t("Document Comparison & Audit Workspace")}</h2>
                  <p className="text-xs text-neutral-500">{t("Compare reference SI values with target BL data. Editable fields allow direct overrides.")}</p>
                </div>
                <span className="text-xs font-bold text-neutral-500 bg-neutral-100 px-2.5 py-1 rounded-md">
                  {comparisons?.length || 0} {t("Fields Checked")}
                </span>
              </div>

              {/* Scrollable Field List */}
              <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {comparisons?.map((field) => {
                  const isMismatched = field.status !== 'match';
                  const isUncertain = field.status === 'uncertain';
                  return (
                    <div 
                      key={field.field} 
                      className={`p-4 rounded-xl border transition-all ${
                        isMismatched ? 'border-amber-200 bg-amber-50/30' : 'border-neutral-200 bg-neutral-50/50'
                      }`}
                    >
                      <div className="flex justify-between items-center mb-2">
                        <button
                          type="button"
                          onClick={() => {
                            setFocusField(field.field);
                            if (activeTab === "EMAIL") setActiveTab("SI");
                          }}
                          title={t("Show this field in the source documents")}
                          className="text-xs font-extrabold text-neutral-700 uppercase tracking-wider hover:text-blue-700 cursor-pointer"
                        >
                          {t(field.field.replace(/_/g, " "))} ↗
                        </button>
                        {isMismatched && (
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-extrabold uppercase tracking-wider ${
                            isUncertain ? "bg-neutral-200 text-neutral-700" : "bg-amber-200 text-amber-900"
                          }`}>
                            {isUncertain ? t("Uncertain") : t("Mismatch")}
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 gap-4 text-sm mt-2 pt-2 border-t border-neutral-200/60">
                        {/* SI Reference (Read-only) */}
                        <div>
                          <span className="text-neutral-400 text-[10px] font-bold uppercase tracking-wider block mb-1">{t("SI (Reference)")}</span>
                          <span className="font-semibold text-neutral-900 block truncate">
                            {field.si?.raw || field.si?.value || "—"}
                            {field.si?.method === "ocr" && (
                              <span className="ml-1.5 text-[10px] font-bold text-amber-600">{t("OCR")}</span>
                            )}
                          </span>
                        </div>

                        {/* BL Target / Editable Input */}
                        <div>
                          <span className="text-neutral-400 text-[10px] font-bold uppercase tracking-wider block mb-1">
                            {t("BL (Target Value)")}
                            {field.bl?.method === "ocr" && (
                              <span className="ml-1.5 text-amber-600">{t("· OCR, verify")}</span>
                            )}
                          </span>
                          {corrections[field.field] !== undefined ? (
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
                })}
              </div>

              {/* Sticky Action Footer for Corrections */}
              <div className="mt-4 pt-4 border-t border-neutral-200 bg-white">
                <button 
                  onClick={handleBatchCorrection}
                  disabled={isSubmitting}
                  className="w-full bg-rose-600 hover:bg-rose-700 text-white font-bold px-4 py-3 rounded-xl text-sm disabled:opacity-50 transition-colors shadow-sm cursor-pointer"
                >
                  {isSubmitting ? t("Submitting All Changes...") : t("Confirm & Save All Corrections")}
                </button>
              </div>
            </div>
          )}

        
        </div>
      </div>

      {hasComparisons && (
        <div className="mt-8">
          <SideBySide emailId={emailId} focusField={focusField} />
        </div>
      )}
    </div>
  );
}
