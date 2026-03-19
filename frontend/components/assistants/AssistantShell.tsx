"use client";

import { useState, useEffect, useRef } from "react";
import {
  fetchPresets,
  fetchAskPreset,
  fetchAskCustom,
  type AssistantType,
  type AssistantAnswer,
  type PresetQuestion,
} from "@/lib/api";
import { useLocale } from "@/lib/i18n/LocaleContext";
import { getT } from "@/lib/i18n/translations";

interface Props {
  assistantType: AssistantType;
}

export function AssistantShell({ assistantType }: Props) {
  const { locale } = useLocale();
  const t = getT(locale).assistant;

  const [presets, setPresets] = useState<PresetQuestion[]>([]);
  const [accordionOpen, setAccordionOpen] = useState(false);
  const [customQuery, setCustomQuery] = useState("");
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const title = assistantType === "knowledge" ? t.knowledgeTitle : t.analystTitle;
  const desc = assistantType === "knowledge" ? t.knowledgeDesc : t.analystDesc;

  // Reload presets when locale changes
  useEffect(() => {
    fetchPresets(assistantType, locale)
      .then((res) => setPresets(res.questions))
      .catch(() => setPresets([]));
  }, [assistantType, locale]);

  async function askPreset(preset: PresetQuestion) {
    setAccordionOpen(false);
    setCustomQuery(preset.text);
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const res = await fetchAskPreset(assistantType, preset.id, locale);
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
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-emerald-400">{title}</h1>
          <p className="mt-1 text-slate-400">{desc}</p>
        </div>
        <button
          onClick={() => {
            setAnswer(null);
            setError(null);
            setCustomQuery("");
            fetchPresets(assistantType, locale)
              .then((res) => setPresets(res.questions))
              .catch(() => setPresets([]));
          }}
          className="ml-4 mt-1 rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-400 hover:border-emerald-500 hover:text-emerald-400 transition-colors"
          title={t.refresh}
        >
          ↺ {t.refresh}
        </button>
      </div>

      {/* Accordion — preset questions */}
      {presets.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/20">
          <button
            onClick={() => setAccordionOpen((o) => !o)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <span className="text-sm font-medium text-slate-300">
              {t.presetQuestions}
              <span className="ml-2 text-xs text-slate-500">({presets.length})</span>
            </span>
            <span className="text-slate-500 transition-transform" style={{ transform: accordionOpen ? "rotate(180deg)" : "none" }}>
              ▾
            </span>
          </button>

          {accordionOpen && (
            <div className="border-t border-slate-700">
              {presets.map((p) => (
                <button
                  key={p.id}
                  onClick={() => askPreset(p)}
                  disabled={loading}
                  className="flex w-full items-center gap-2 border-b border-slate-800 px-4 py-2.5 text-left text-sm text-slate-300 hover:bg-slate-700/50 hover:text-white last:border-b-0 disabled:opacity-50 transition-colors"
                >
                  <span className="text-emerald-500 text-xs shrink-0">▶</span>
                  {p.text}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-3">
        <input
          ref={inputRef}
          value={customQuery}
          onChange={(e) => setCustomQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && askCustom()}
          placeholder={t.placeholder}
          className="flex-1 rounded border border-slate-600 bg-slate-900 px-4 py-2.5 text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
        />
        <button
          onClick={askCustom}
          disabled={loading || !customQuery.trim()}
          className="rounded bg-emerald-600 px-5 py-2.5 font-medium text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
        >
          {loading ? t.asking : t.ask}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded border border-red-800 bg-red-900/20 px-4 py-3 text-sm text-red-400">
          {t.error}: {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-slate-400">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-400" />
          <span className="text-sm">{t.asking}</span>
        </div>
      )}

      {/* Answer */}
      {answer && !loading && (
        <div className="space-y-3 rounded-lg border border-slate-700 bg-slate-800/30 p-5">
          <div className="flex items-center gap-2">
            <p className="text-xs text-slate-500 italic">{answer.query}</p>
            {answer.cached && (
              <span className="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">
                {t.cached}
              </span>
            )}
          </div>

          <p className="whitespace-pre-wrap text-slate-200 leading-relaxed">
            {answer.answer || t.noAnswer}
          </p>

          {answer.used_tools.length > 0 && (
            <div className="border-t border-slate-700 pt-3">
              <p className="text-xs font-medium text-slate-400 mb-1">{t.tools}</p>
              <div className="flex flex-wrap gap-1">
                {answer.used_tools.map((tool, i) => (
                  <span key={i} className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {answer.citations.length > 0 && (
            <div className="border-t border-slate-700 pt-3">
              <p className="text-xs font-medium text-slate-400 mb-2">{t.sources}</p>
              <ul className="space-y-1">
                {answer.citations.map((c, i) => (
                  <li key={i} className="rounded border border-slate-700 bg-slate-900/50 px-3 py-1.5 text-xs text-slate-400">
                    <span className="font-medium text-slate-300">{c.source}</span>
                    {c.excerpt && (
                      <span className="ml-2 text-slate-500">— {c.excerpt.slice(0, 100)}…</span>
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
