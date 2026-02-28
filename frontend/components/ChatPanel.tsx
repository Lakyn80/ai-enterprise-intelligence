"use client";

import { useState } from "react";
import { fetchChat } from "@/lib/api";

export function ChatPanel() {
  const [message, setMessage] = useState("");
  const [provider, setProvider] = useState<"openai" | "deepseek">("openai");
  const [answer, setAnswer] = useState("");
  const [usedTools, setUsedTools] = useState<string[]>([]);
  const [citations, setCitations] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    if (!message.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer("");
    setUsedTools([]);
    setCitations([]);
    try {
      const res = await fetchChat(message, provider);
      setAnswer(res.answer);
      setUsedTools(res.used_tools || []);
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
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value as "openai" | "deepseek")}
          className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white"
        >
          <option value="openai">OpenAI</option>
          <option value="deepseek">DeepSeek</option>
        </select>
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about forecasts, e.g. What happens if we increase price by 5%?"
          className="flex-1 rounded border border-slate-600 bg-slate-900 px-4 py-2 text-white placeholder-slate-500"
        />
        <button
          onClick={send}
          disabled={loading}
          className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
      {error && <div className="text-sm text-red-400">{error}</div>}
      {answer && (
        <div className="space-y-2 rounded border border-slate-600 bg-slate-900/50 p-4">
          <p className="text-slate-200 whitespace-pre-wrap">{answer}</p>
          {usedTools.length > 0 && (
            <p className="text-xs text-slate-500">Tools: {usedTools.join(", ")}</p>
          )}
          {citations.length > 0 && (
            <div className="mt-2 border-t border-slate-700 pt-2">
              <p className="text-xs font-medium text-slate-400">Citations</p>
              <ul className="mt-1 list-inside list-disc text-xs text-slate-500">
                {citations.map((c, i) => (
                  <li key={i}>{String((c as { document_id?: string }).document_id ?? c)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
