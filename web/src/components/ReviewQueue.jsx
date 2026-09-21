import { useEffect, useState } from "react";
import { getReviewQueue } from "../data/reports";
import ReportView from "./ReportView";
import { useT } from "../i18n"; // Import your powerful new view!

export default function ReviewQueue() {
  const t = useT();
  const [queue, setQueue] = useState([]);
  const [selectedEmailId, setSelectedEmailId] = useState(null);

  // Fetch the queue from the backend
  const loadQueue = () => {
    getReviewQueue().then(setQueue);
  };

  useEffect(() => {
    loadQueue();
  }, []);

  if (selectedEmailId) {
    return (
      <ReportView 
        emailId={selectedEmailId} 
        onBack={() => {
          setSelectedEmailId(null);
          loadQueue(); // Refresh the list so the completed item disappears
        }} 
      />
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-8 pb-12">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-neutral-900">{t("Action Required")}</h2>
          <p className="text-sm text-neutral-500 mt-1">{t("Cases escalated for human review")}</p>
        </div>
        <span className="bg-rose-100 text-rose-800 text-xs font-bold px-3 py-1 rounded-full">
          {queue.length} {t("Cases")}
        </span>
      </div>

      <div className="border border-neutral-200 rounded-xl divide-y divide-neutral-100 bg-white shadow-xs overflow-hidden">
        {queue.length === 0 ? (
          <div className="p-12 text-center text-neutral-500 font-medium">
            {t("No items in the review queue! You're all caught up.")}
          </div>
        ) : (
          queue.map((item) => (
            <button
              key={item.email_id}
              onClick={() => setSelectedEmailId(item.email_id)}
              className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-rose-50/50 transition-all group"
            >
              <div>
                <p className="text-sm font-bold text-neutral-900 group-hover:text-rose-700 transition-colors">
                  {item.email_id}
                </p>
                <p className="text-[10px] text-rose-500 font-extrabold uppercase tracking-wider mt-1">
                  ↳ {t(item.review_reason?.replace(/_/g, " ") || "NEEDS REVIEW")}
                </p>
              </div>
              
              {/* Call to action button on the row */}
              <span className="text-xs font-bold px-4 py-2 rounded-lg bg-neutral-900 text-white group-hover:bg-rose-600 transition-colors shadow-sm">
                {t("Open Workspace")}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}