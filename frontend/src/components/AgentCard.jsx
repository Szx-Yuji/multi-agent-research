const AGENT_COLORS = {
  Planner: "bg-blue-100 text-blue-700 border-blue-200",
  Researcher: "bg-purple-100 text-purple-700 border-purple-200",
  Analyst: "bg-amber-100 text-amber-700 border-amber-200",
  Writer: "bg-green-100 text-green-700 border-green-200",
  Error: "bg-red-100 text-red-700 border-red-200",
};

function formatDetail(detail) {
  if (Array.isArray(detail)) {
    return (
      <ul className="mt-1 space-y-0.5">
        {detail.map((item, i) => (
          <li key={i} className="text-gray-600 text-xs">
            • {item}
          </li>
        ))}
      </ul>
    );
  }
  if (typeof detail === "string" && detail.length > 120) {
    return (
      <p className="text-gray-500 text-xs mt-0.5 break-words">
        {detail.slice(0, 120)}…
      </p>
    );
  }
  return detail ? (
    <p className="text-gray-500 text-xs mt-0.5 break-words">{detail}</p>
  ) : null;
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function AgentCard({ log, isNew }) {
  const colorClass = AGENT_COLORS[log.agent] ?? "bg-gray-100 text-gray-700 border-gray-200";

  return (
    <div
      className={`flex items-start gap-3 p-3 rounded-xl bg-white border border-gray-100 shadow-sm transition-all duration-300 ${
        isNew ? "animate-slide-in" : ""
      }`}
    >
      <span
        className={`shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full border ${colorClass}`}
      >
        {log.agent}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-gray-800">{log.action}</span>
          <span className="text-xs text-gray-400 shrink-0">
            {formatTime(log.timestamp)}
          </span>
        </div>
        {formatDetail(log.detail)}
      </div>
    </div>
  );
}
