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
    <div className="min-h-screen">
      <Nav view={view === "report" ? "inbox" : view} setView={setView} />
      {view === "inbox" && <InboxView onSelect={openReport} />}
      {view === "report" && (
        <ReportView emailId={selectedEmail} onBack={() => setView("inbox")} />
      )}
      {view === "review" && <ReviewQueue />}
    </div>
  );
}
