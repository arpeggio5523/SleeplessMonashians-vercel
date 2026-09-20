export default function Nav({ view, setView }) {
  const tabs = [
    { id: "inbox", label: "Inbox" },
    { id: "review", label: "Review Queue" },
  ];

  return (
    <nav className="border-b border-neutral-200 bg-white">
      <div className="max-w-5xl mx-auto flex gap-1 px-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setView(t.id)}
            className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
              view === t.id
                ? "border-neutral-900 text-neutral-900"
                : "border-transparent text-neutral-500 hover:text-neutral-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
