export default function Home() {
  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-emerald-400">
        Retail Forecast Platform
      </h1>
      <p className="max-w-xl text-slate-400">
        Data-driven forecasting and AI-powered decision support for retail.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <a
          href="/forecast"
          className="rounded-lg border border-slate-700 bg-slate-800/50 p-6 transition hover:border-emerald-500/50"
        >
          <h2 className="font-semibold text-white">Forecast</h2>
          <p className="mt-2 text-sm text-slate-400">
            View demand forecasts and run price scenarios.
          </p>
        </a>
        <a
          href="/assistant"
          className="rounded-lg border border-slate-700 bg-slate-800/50 p-6 transition hover:border-emerald-500/50"
        >
          <h2 className="font-semibold text-white">AI Assistant</h2>
          <p className="mt-2 text-sm text-slate-400">
            Ask questions about forecasts and data.
          </p>
        </a>
        <a
          href="/knowledge"
          className="rounded-lg border border-slate-700 bg-slate-800/50 p-6 transition hover:border-emerald-500/50"
        >
          <h2 className="font-semibold text-white">Knowledge</h2>
          <p className="mt-2 text-sm text-slate-400">
            Query internal documents and reports.
          </p>
        </a>
      </div>
    </div>
  );
}
