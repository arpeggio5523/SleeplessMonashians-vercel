export default function Nav({ view, setView }) {
  return (
    <nav className="bg-white border-b border-neutral-200 mb-8 shadow-xs">
      <div className="max-w-7xl mx-auto px-8 flex gap-8">
        <button
          onClick={() => setView("inbox")}
          className={`py-4 text-sm font-bold border-b-2 transition-colors ${
            view === "inbox" || view === "report"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-neutral-500 hover:text-neutral-700"
          }`}
        >
          Inbox Dashboard
        </button>
        <button
          onClick={() => setView("review")}
          className={`py-4 text-sm font-bold border-b-2 transition-colors ${
            view === "review"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-neutral-500 hover:text-neutral-700"
          }`}
        >
          Review Queue
        </button>
      </div>
    </nav>
  );
}