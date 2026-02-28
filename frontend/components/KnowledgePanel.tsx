"use client";

import { useState } from "react";
import { fetchKnowledgeQuery } from "@/lib/api";

export function KnowledgePanel() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer("");
    setCitations([]);
    try {
      const res = await fetchKnowledgeQuery(query);
      setAnswer(res.answer);
      setCitations(res.citations || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-800/30 p-6">
      <div className="flex gap-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search internal documents..."
          className="flex-1 rounded border border-slate-600 bg-slate-900 px-4 py-2 text-white placeholder-slate-500"
        />
        <button
          onClick={search}
          disabled={loading}
          className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "Searching..." : "Query"}
        </button>
      </div>
      {error && <div className="text-sm text-red-400">{error}</div>}
      {answer && (
        <div className="space-y-2 rounded border border-slate-600 bg-slate-900/50 p-4">
          <p className="text-slate-200 whitespace-pre-wrap">{answer}</p>
          {citations.length > 0 && (
            <div className="mt-4 border-t border-slate-700 pt-4">
              <p className="text-sm font-medium text-slate-400">Citations</p>
              <ul className="mt-2 space-y-2">
                {citations.map((c, i) => (
                  <li
                    key={i}
                    className="rounded border border-slate-700 bg-slate-800/50 p-2 text-sm text-slate-300"
                  >
                    {typeof c === "object" && c !== null && "document_id" in c
                      ? String(c.document_id)
                      : JSON.stringify(c)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
