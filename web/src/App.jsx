import { useState } from "react";
import Nav from "./components/Nav.jsx";
import InboxView from "./components/InboxView.jsx";
import ReportView from "./components/ReportView.jsx";
import ReviewQueue from "./components/ReviewQueue.jsx";

export default function App() {
  const [view, setView] = useState("inbox");
  const [selectedEmail, setSelectedEmail] = useState(null);

  function openReport(emailId) {
    setSelectedEmail(emailId);
    setView("report");
  }

  return (
    <div className="min-h-screen bg-neutral-50 pb-12">
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