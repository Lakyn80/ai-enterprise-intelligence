"use client";

import { useState, useEffect } from "react";
import {
  fetchPresets,
  fetchAskPreset,
  fetchAskCustom,
  type AssistantType,
  type AssistantAnswer,
  type PresetQuestion,
} from "@/lib/api";
import { useTranslation, type Locale } from "@/lib/i18n/useTranslation";

const LOCALES: { value: Locale; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "cs", label: "CS" },
  { value: "sk", label: "SK" },
  { value: "ru", label: "RU" },
];

interface Props {
  assistantType: AssistantType;
  title: string;
  description: string;
}

export function AssistantShell({ assistantType, title, description }: Props) {
  const { locale, setLocale, tr } = useTranslation("en");
  const [presets, setPresets] = useState<PresetQuestion[]>([]);
  const [customQuery, setCustomQuery] = useState("");
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load presets whenever locale changes
  useEffect(() => {
    fetchPresets(assistantType, locale)
      .then((res) => setPresets(res.questions))
      .catch(() => setPresets([]));
  }, [assistantType, locale]);

  async function askPreset(questionId: string) {
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const res = await fetchAskPreset(assistantType, questionId, locale);
      setAnswer(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function askCustom() {
    if (!customQuery.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const res = await fetchAskCustom(assistantType, customQuery, locale);
      setAnswer(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-emerald-400">{title}</h1>
          <p className="mt-1 text-slate-400">{description}</p>
        </div>
        {/* Locale switcher */}
        <div className="flex gap-1 shrink-0">
          {LOCALES.map((l) => (
            <button
              key={l.value}
              onClick={() => setLocale(l.value)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                locale === l.value
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:bg-slate-600"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Preset questions */}
      {presets.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-400">{tr.presetQuestions}</p>
          <div className="flex flex-wrap gap-2">
            {presets.map((p) => (
              <button
                key={p.id}
                onClick={() => askPreset(p.id)}
                disabled={loading}
                className="rounded-full border border-slate-600 bg-slate-800/50 px-3 py-1.5 text-sm text-slate-300 hover:border-emerald-500 hover:text-white disabled:opacity-50 transition-colors text-left"
              >
                {p.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Custom input */}
      <div className="flex gap-3">
        <input
          value={customQuery}
          onChange={(e) => setCustomQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && askCustom()}
          placeholder={tr.customQuestion}
          className="flex-1 rounded border border-slate-600 bg-slate-900 px-4 py-2 text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
        />
        <button
          onClick={askCustom}
          disabled={loading || !customQuery.trim()}
          className="rounded bg-emerald-600 px-5 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
        >
          {loading ? tr.asking : tr.ask}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded border border-red-800 bg-red-900/20 px-4 py-3 text-sm text-red-400">
          {tr.errorPrefix}: {error}
        </div>
      )}

      {/* Loading spinner */}
      {loading && (
        <div className="flex items-center gap-2 text-slate-400">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-400" />
          <span className="text-sm">{tr.asking}</span>
        </div>
      )}

      {/* Answer */}
      {answer && !loading && (
        <div className="space-y-3 rounded-lg border border-slate-700 bg-slate-800/30 p-5">
          {/* Query + cached badge */}
          <div className="flex items-center gap-2">
            <p className="text-xs text-slate-500 italic">{answer.query}</p>
            {answer.cached && (
              <span className="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">
                {tr.cachedBadge}
              </span>
            )}
          </div>

          {/* Answer text */}
          <p className="whitespace-pre-wrap text-slate-200">{answer.answer || tr.noAnswer}</p>

          {/* Used tools */}
          {answer.used_tools.length > 0 && (
            <div className="border-t border-slate-700 pt-3">
              <p className="text-xs font-medium text-slate-400">{tr.usedTools}</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {answer.used_tools.map((tool, i) => (
                  <span
                    key={i}
                    className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Citations */}
          {answer.citations.length > 0 && (
            <div className="border-t border-slate-700 pt-3">
              <p className="text-xs font-medium text-slate-400">{tr.citations}</p>
              <ul className="mt-2 space-y-1">
                {answer.citations.map((c, i) => (
                  <li
                    key={i}
                    className="rounded border border-slate-700 bg-slate-900/50 px-3 py-2 text-xs text-slate-400"
                  >
                    <span className="font-medium text-slate-300">{c.source}</span>
                    {c.excerpt && (
                      <span className="ml-2 text-slate-500">— {c.excerpt.slice(0, 120)}…</span>
                    )}
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
