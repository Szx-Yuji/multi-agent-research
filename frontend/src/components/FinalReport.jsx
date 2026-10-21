import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function getDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function SourceCard({ source }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col gap-0.5 p-3 bg-white border border-gray-200 rounded-xl hover:border-indigo-300 hover:shadow-sm transition group"
    >
      <span className="text-xs font-medium text-indigo-600 group-hover:text-indigo-700 line-clamp-2">
        {source.title || source.url}
      </span>
      <span className="text-xs text-gray-400">{getDomain(source.url)}</span>
    </a>
  );
}

export default function FinalReport({ report, sources, streaming = false }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={streaming ? "" : "animate-fade-in"}>
      {/* Report header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Research Report</h2>
        {streaming ? (
          <span className="flex items-center gap-2 text-xs font-medium text-indigo-600">
            <span className="inline-block w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            Writing…
          </span>
        ) : (
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 active:bg-gray-100 transition"
          >
            {copied ? "✓ Copied!" : "Copy Markdown"}
          </button>
        )}
      </div>

      {/* Markdown report */}
      <div className="prose prose-sm prose-gray max-w-none bg-white border border-gray-200 rounded-2xl p-6 mb-6 shadow-sm">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
      </div>

      {/* Sources */}
      {sources.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Sources ({sources.length})
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {sources.map((s, i) => (
              <SourceCard key={i} source={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
