import { useEffect, useRef } from "react";
import AgentCard from "./AgentCard";

const STATIONS = [
  {
    key: "Planner",
    icon: "🗂️",
    label: "Planner",
    desc: "Breaks question into sub-tasks",
    color: "border-blue-300 bg-blue-50",
    activeRing: "ring-2 ring-blue-400",
    dot: "bg-blue-400",
  },
  {
    key: "Researcher",
    icon: "🔍",
    label: "Researcher",
    desc: "Searches the web",
    color: "border-purple-300 bg-purple-50",
    activeRing: "ring-2 ring-purple-400",
    dot: "bg-purple-400",
  },
  {
    key: "Analyst",
    icon: "🧠",
    label: "Analyst",
    desc: "Synthesizes findings",
    color: "border-amber-300 bg-amber-50",
    activeRing: "ring-2 ring-amber-400",
    dot: "bg-amber-400",
  },
  {
    key: "Writer",
    icon: "✍️",
    label: "Writer",
    desc: "Writes the report",
    color: "border-green-300 bg-green-50",
    activeRing: "ring-2 ring-green-400",
    dot: "bg-green-400",
  },
];

function stationStatus(key, logs, currentAgent) {
  // Current wins over log history: the Analyst and Writer stream output long
  // before they log anything, so keying off logs alone would leave the pipeline
  // showing nothing active for most of a run.
  if (currentAgent === key) return "active";
  return logs.some((l) => l.agent === key) ? "done" : "waiting";
}

export default function AgentTimeline({ logs, currentAgent, status }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <div className="flex flex-col gap-6">
      {/* Station pipeline */}
      <div className="flex items-center gap-2 flex-wrap">
        {STATIONS.map((s, idx) => {
          const st = stationStatus(s.key, logs, currentAgent);
          const isActive = st === "active";
          const isDone = st === "done";

          return (
            <div key={s.key} className="flex items-center gap-2">
              <div
                className={`flex items-center gap-2 px-3 py-2 rounded-xl border transition-all duration-300 ${s.color} ${
                  isActive ? s.activeRing + " shadow-md" : ""
                } ${isDone ? "opacity-80" : ""} ${st === "waiting" ? "opacity-40" : ""}`}
              >
                <span className="text-lg">{s.icon}</span>
                <div>
                  <div className="text-xs font-semibold text-gray-800 flex items-center gap-1.5">
                    {s.label}
                    {isActive && (
                      <span className={`inline-block w-2 h-2 rounded-full ${s.dot} animate-pulse`} />
                    )}
                    {isDone && <span className="text-green-500">✓</span>}
                  </div>
                  <div className="text-xs text-gray-500 hidden sm:block">{s.desc}</div>
                </div>
              </div>
              {idx < STATIONS.length - 1 && (
                <span className="text-gray-300 font-bold text-lg select-none">→</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Log feed */}
      <div className="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1">
        {logs.length === 0 && (
          <p className="text-sm text-gray-400 italic">Agent activity will appear here…</p>
        )}
        {logs.map((log, i) => (
          <AgentCard key={i} log={log} isNew={i === logs.length - 1} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
