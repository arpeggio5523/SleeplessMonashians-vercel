import { useState } from "react";
import Nav from "./components/Nav.jsx";
import InboxView from "./components/InboxView.jsx";
import ReportView from "./components/ReportView.jsx";
import ReviewQueue from "./components/ReviewQueue.jsx";
import { useToastStore } from "./store/useToastStore.js";

export default function App() {
  const [view, setView] = useState("inbox");
  const [selectedEmail, setSelectedEmail] = useState(null);

  const toastMessage = useToastStore((state) => state.message)

  function openReport(emailId) {
    setSelectedEmail(emailId);
    setView("report");
  }

  return (
    <div className="min-h-screen bg-neutral-50 pb-12">

      {toastMessage && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold px-5 py-3 rounded-xl shadow-md flex items-center gap-2 animate-fade-in">
          <span className="bg-emerald-600 text-white rounded-full w-4 h-4 flex items-center justify-center text-[10px]">✓</span> 
          {toastMessage}
        </div>
      )}
      <Nav view={view} setView={(tab) => { setView(tab); setSelectedEmail(null); }} />
      
      {/* Changed max-w-5xl to max-w-7xl so it spans the entire screen cleanly */}
      <main className="max-w-7xl mx-auto px-8 w-full">
        {view === "inbox" && <InboxView onSelect={openReport} />}
        {view === "report" && (
          <ReportView emailId={selectedEmail} onBack={() => setView("inbox")} />
        )}
        {view === "review" && <ReviewQueue onSelect={openReport} />}
      </main>
    </div>
  );
}