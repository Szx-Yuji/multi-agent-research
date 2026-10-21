const EXAMPLES = [
  "What are the latest breakthroughs in quantum computing?",
  "How does Anthropic's approach to AI safety compare to OpenAI's?",
  "What are the most effective treatments for insomnia?",
];

export default function QueryInput({ onSubmit, disabled }) {
  function handleExample(text) {
    if (!disabled) onSubmit(text);
  }

  function handleSubmit(e) {
    e.preventDefault();
    const value = e.target.elements.query.value.trim();
    if (value) onSubmit(value);
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="text-center mb-10">
        <h1 className="text-4xl font-bold text-gray-900 mb-3 tracking-tight">
          Multi-Agent Research Assistant
        </h1>
        <p className="text-gray-500 text-lg">
          Ask any research question — specialized AI agents collaborate to answer it.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="relative">
          <input
            name="query"
            type="text"
            autoFocus
            placeholder="Ask a research question..."
            disabled={disabled}
            className="w-full px-5 py-4 pr-32 text-gray-900 bg-white border border-gray-200 rounded-2xl shadow-sm text-base focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400 transition"
          />
          <button
            type="submit"
            disabled={disabled}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 active:bg-indigo-800 disabled:bg-indigo-300 disabled:cursor-not-allowed transition"
          >
            {disabled ? "Researching…" : "Research"}
          </button>
        </div>
      </form>

      <div className="flex flex-wrap gap-2 justify-center">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => handleExample(ex)}
            disabled={disabled}
            className="px-3 py-1.5 text-xs text-indigo-700 bg-indigo-50 border border-indigo-100 rounded-full hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
