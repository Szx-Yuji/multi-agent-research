import { useEffect, useState } from "react";
import { api } from "../api";

export default function HistoryPanel({ open, onClose, onOpenRun, refreshKey }) {
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    api
      .history()
      .then((d) => setRuns(d.runs))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [open, refreshKey]);

  async function handleDelete(e, id) {
    e.stopPropagation();
    const previous = runs;
    setRuns((rs) => rs.filter((r) => r.id !== id));
    try {
      await api.deleteHistoryItem(id);
    } catch {
      setRuns(previous); // put it back if the server refused
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end bg-gray-900/30"
      onClick={onClose}
    >
      <aside
        className="w-full max-w-md h-full bg-white shadow-xl overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            History
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-sm"
          >
            Close
          </button>
        </div>

        <div className="p-4 space-y-2">
          {loading && <p className="text-sm text-gray-500 px-1">Loading…</p>}
          {error && <p className="text-sm text-red-600 px-1">{error}</p>}
          {!loading && !error && runs.length === 0 && (
            <p className="text-sm text-gray-500 px-1">
              No saved research yet. Runs are saved automatically while you are
              signed in.
            </p>
          )}

          {runs.map((run) => (
            <div
              key={run.id}
              role="button"
              tabIndex={0}
              onClick={() => onOpenRun(run.id)}
              onKeyDown={(e) => e.key === "Enter" && onOpenRun(run.id)}
              className="w-full text-left p-3 border border-gray-200 rounded-xl hover:border-indigo-300 hover:bg-indigo-50/40 transition group cursor-pointer"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-medium text-gray-800 line-clamp-2">
                  {run.query}
                </span>
                <button
                  onClick={(e) => handleDelete(e, run.id)}
                  className="shrink-0 text-xs text-gray-300 group-hover:text-red-500 transition"
                  title="Delete"
                  aria-label="Delete this run"
                >
                  ✕
                </button>
              </div>
              <div className="mt-1 text-xs text-gray-400">
                {new Date(run.created_at).toLocaleString()} · {run.source_count}{" "}
                sources · {run.duration_seconds}s
              </div>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
