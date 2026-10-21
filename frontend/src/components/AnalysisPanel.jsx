import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function AnalysisPanel({ text, streaming, collapsed }) {
  const [open, setOpen] = useState(true);
  const [userToggled, setUserToggled] = useState(false);
  const bodyRef = useRef(null);

  // Collapse once the report starts, unless the user has taken control.
  useEffect(() => {
    if (collapsed && !userToggled) setOpen(false);
  }, [collapsed, userToggled]);

  // Keep the newest text in view while it streams.
  useEffect(() => {
    if (open && streaming && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [text, open, streaming]);

  if (!text) return null;

  return (
    <section className="mb-8 bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <button
        onClick={() => {
          setUserToggled(true);
          setOpen((v) => !v);
        }}
        className="w-full flex items-center justify-between gap-3 px-5 py-3 text-left hover:bg-gray-50 transition"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-gray-600 uppercase tracking-wide">
          <span
            className={`inline-block text-gray-400 transition-transform ${
              open ? "rotate-90" : ""
            }`}
          >
            ▸
          </span>
          Analysis
        </span>
        {streaming ? (
          <span className="flex items-center gap-2 text-xs font-medium text-indigo-600">
            <span className="inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            Synthesizing…
          </span>
        ) : (
          <span className="text-xs text-gray-400">
            {open ? "Hide" : "Show"}
          </span>
        )}
      </button>

      {open && (
        <div
          ref={bodyRef}
          className="px-5 pb-5 max-h-72 overflow-y-auto"
        >
          {/* Rendered, not raw: the Analyst writes Markdown and it sits
              directly above the rendered report. */}
          <div className="prose prose-sm max-w-none prose-headings:text-gray-700 prose-p:text-gray-700">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
          </div>
          {streaming && (
            <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse" />
          )}
        </div>
      )}
    </section>
  );
}
