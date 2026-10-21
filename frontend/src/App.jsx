import { useState, useRef, useEffect } from "react";
import QueryInput from "./components/QueryInput";
import AgentTimeline from "./components/AgentTimeline";
import AnalysisPanel from "./components/AnalysisPanel";
import FinalReport from "./components/FinalReport";
import AuthPanel from "./components/AuthPanel";
import HistoryPanel from "./components/HistoryPanel";
import { API_URL, api, getToken, setToken } from "./api";

const INITIAL_STATE = {
  status: "idle",
  agentLogs: [],
  finalReport: "",
  // Accumulated from `analysis_token` / `report_token` events so both appear
  // progressively instead of arriving whole when the run ends.
  streamingAnalysis: "",
  streamingReport: "",
  subTasks: [],
  sources: [],
  currentAgent: "",
  errorMessage: "",
  saved: false,
};

export default function App() {
  const [state, setState] = useState(INITIAL_STATE);
  const [query, setQuery] = useState("");
  const [email, setEmail] = useState(null);
  const [showAuth, setShowAuth] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const esRef = useRef(null);

  useEffect(() => {
    return () => esRef.current?.close();
  }, []);

  // Restore a previous session, and drop the token if the server rejects it.
  useEffect(() => {
    if (!getToken()) return;
    api
      .me()
      .then((u) => setEmail(u.email))
      .catch(() => setToken(null));
  }, []);

  async function handleSubmit(q) {
    esRef.current?.close();
    setQuery(q);
    setState({ ...INITIAL_STATE, status: "running" });

    let sessionId;
    try {
      const data = await api.startResearch(q);
      sessionId = data.session_id;
    } catch (err) {
      setState((s) => ({
        ...s,
        status: "error",
        errorMessage: err.message ?? "Failed to start research",
      }));
      return;
    }

    // EventSource cannot send an Authorization header, which is fine: the
    // session id is the capability, and the run was already associated with
    // the account at POST time.
    const es = new EventSource(`${API_URL}/api/research/${sessionId}/stream`);
    esRef.current = es;

    es.addEventListener("agent_update", (e) => {
      const log = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        agentLogs: [...s.agentLogs, log],
        currentAgent: log.agent,
      }));
    });

    // Streaming output is the earliest signal an agent has started. Its log
    // entry only lands when it finishes, so without this the pipeline would
    // still show the previous agent as active while this one is producing text.
    es.addEventListener("analysis_token", (e) => {
      const { text } = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        streamingAnalysis: s.streamingAnalysis + text,
        currentAgent: "Analyst",
      }));
    });

    es.addEventListener("report_token", (e) => {
      const { text } = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        streamingReport: s.streamingReport + text,
        currentAgent: "Writer",
      }));
    });

    es.addEventListener("complete", (e) => {
      const payload = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        status: "complete",
        finalReport: payload.final_report,
        subTasks: payload.sub_tasks,
        sources: payload.sources,
        saved: Boolean(payload.saved),
        currentAgent: "",
      }));
      if (payload.saved) setHistoryKey((k) => k + 1);
      es.close();
    });

    es.addEventListener("error", (e) => {
      if (e.data) {
        const payload = JSON.parse(e.data);
        setState((s) => ({
          ...s,
          status: "error",
          errorMessage: payload.message ?? "An error occurred",
        }));
      } else {
        setState((s) =>
          s.status === "running"
            ? { ...s, status: "error", errorMessage: "Connection lost" }
            : s
        );
      }
      es.close();
    });
  }

  function handleReset() {
    esRef.current?.close();
    setState(INITIAL_STATE);
    setQuery("");
  }

  function handleSignOut() {
    setToken(null);
    setEmail(null);
    setShowHistory(false);
  }

  async function handleOpenRun(id) {
    try {
      const run = await api.historyItem(id);
      esRef.current?.close();
      setQuery(run.query);
      setState({
        ...INITIAL_STATE,
        status: "complete",
        finalReport: run.final_report,
        subTasks: run.sub_tasks,
        sources: run.sources,
        saved: true,
      });
      setShowHistory(false);
    } catch (err) {
      setState((s) => ({ ...s, status: "error", errorMessage: err.message }));
    }
  }

  const isRunning = state.status === "running";
  const showResults = state.status !== "idle";

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="absolute top-0 right-0 p-4 flex items-center gap-3 text-xs z-30">
        {email ? (
          <>
            <button
              onClick={() => setShowHistory(true)}
              className="px-3 py-1.5 rounded-full bg-white border border-gray-200 text-gray-700 hover:border-indigo-300 transition"
            >
              History
            </button>
            <span className="text-gray-400 hidden sm:inline">{email}</span>
            <button
              onClick={handleSignOut}
              className="text-gray-400 hover:text-gray-600 transition"
            >
              Sign out
            </button>
          </>
        ) : (
          <button
            onClick={() => setShowAuth(true)}
            className="px-3 py-1.5 rounded-full bg-white border border-gray-200 text-gray-700 hover:border-indigo-300 transition"
          >
            Sign in
          </button>
        )}
      </header>

      {!showResults ? (
        <div className="flex items-center justify-center min-h-screen px-4">
          <QueryInput onSubmit={handleSubmit} disabled={isRunning} />
        </div>
      ) : (
        <div className="max-w-5xl mx-auto px-4 py-8">
          <div className="flex items-start justify-between gap-4 mb-8 mt-8">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <button
                  onClick={handleReset}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition"
                >
                  ← New research
                </button>
                {state.saved && (
                  <span className="text-xs text-gray-400">· saved to history</span>
                )}
              </div>
              <h2 className="text-xl font-semibold text-gray-900 max-w-2xl">
                {query}
              </h2>
            </div>
            <StatusBadge status={state.status} />
          </div>

          {state.status === "error" && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
              <strong>Error:</strong> {state.errorMessage || "Something went wrong."}
              <button onClick={handleReset} className="ml-4 underline hover:no-underline">
                Try again
              </button>
            </div>
          )}

          {/* Hidden for a run loaded from history, which has no live timeline */}
          {state.agentLogs.length > 0 && (
            <section className="mb-8 bg-gray-50 border border-gray-200 rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-gray-600 mb-4 uppercase tracking-wide">
                Agent Pipeline
              </h3>
              <AgentTimeline
                logs={state.agentLogs}
                currentAgent={state.currentAgent}
                status={state.status}
              />
            </section>
          )}

          <AnalysisPanel
            text={state.streamingAnalysis}
            streaming={isRunning && !state.streamingReport}
            collapsed={Boolean(state.streamingReport) || state.status === "complete"}
          />

          {state.status === "complete" && state.finalReport && (
            <FinalReport report={state.finalReport} sources={state.sources} />
          )}

          {isRunning && state.streamingReport && (
            <FinalReport report={state.streamingReport} sources={[]} streaming />
          )}

          {isRunning && !state.streamingReport && !state.streamingAnalysis && (
            <div className="flex items-center gap-3 text-gray-500 text-sm">
              <span className="inline-block w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              Agents are working…
            </div>
          )}
        </div>
      )}

      {showAuth && (
        <AuthPanel
          onClose={() => setShowAuth(false)}
          onSignedIn={(e) => {
            setEmail(e);
            setShowAuth(false);
          }}
        />
      )}

      <HistoryPanel
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onOpenRun={handleOpenRun}
        refreshKey={historyKey}
      />
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    running: { label: "Running", cls: "bg-indigo-100 text-indigo-700" },
    complete: { label: "Complete", cls: "bg-green-100 text-green-700" },
    error: { label: "Error", cls: "bg-red-100 text-red-700" },
  };
  const { label, cls } = map[status] ?? {};
  if (!label) return null;
  return (
    <span className={`shrink-0 text-xs font-semibold px-3 py-1 rounded-full ${cls}`}>
      {label}
    </span>
  );
}
