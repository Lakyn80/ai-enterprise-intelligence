"use client";

import { useEffect, useRef, useState } from "react";
import {
  fetchAssistantTrace,
  fetchPresets,
  fetchAskPreset,
  fetchAskCustom,
  type AssistantType,
  type AssistantAnswer,
  type AssistantTrace,
  type Locale,
  type PresetQuestion,
} from "@/lib/api";
import { useLocale } from "@/lib/i18n/LocaleContext";
import { getT } from "@/lib/i18n/translations";

interface Props {
  assistantType: AssistantType;
}

interface ConversationTurn {
  id: string;
  userQuery: string;
  requestQuery: string;
  answer: AssistantAnswer;
  trace: AssistantTrace | null;
  traceOpen: boolean;
  traceLoading: boolean;
  traceError: string | null;
}

interface PendingClarificationContext {
  baseQuery: string;
  clarification: NonNullable<AssistantAnswer["clarification"]>;
}

type ClarificationMetric = "quantity" | "revenue";
type ClarificationScope = "list" | "top_1";

const METRIC_TERMS = {
  revenue: [
    "trz",
    "revenue",
    "vyruck",
    "выруч",
  ],
  quantity: [
    "kusu",
    "kus",
    "pocet",
    "quantity",
    "units",
    "pieces",
    "kolich",
    "колич",
    "штук",
    "объем",
  ],
} as const;

const LIST_SCOPE_TERMS = [
  "produkty",
  "products",
  "список",
  "продукты",
  "seznam",
  "list",
  "top 5",
  "top5",
];

const TOP1_SCOPE_TERMS = [
  "jeden produkt",
  "jeden",
  "single product",
  "single",
  "one product",
  "one",
  "top 1",
  "top1",
  "odin produkt",
  "один продукт",
  "odin",
  "один",
];

const PLURAL_PRODUCT_TERMS = ["produkty", "products", "продукты"];
const SINGULAR_PRODUCT_TERMS = ["produkt", "product", "продукт", "produktu", "продукта"];

function normalizeForFollowUp(input: string) {
  return input
    .trim()
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "");
}

function detectMetric(input: string): ClarificationMetric | null {
  const normalized = normalizeForFollowUp(input);
  if (METRIC_TERMS.revenue.some((term) => normalized.includes(term))) {
    return "revenue";
  }
  if (METRIC_TERMS.quantity.some((term) => normalized.includes(term))) {
    return "quantity";
  }
  return null;
}

function detectScope(input: string): ClarificationScope | null {
  const normalized = normalizeForFollowUp(input);
  if (LIST_SCOPE_TERMS.some((term) => normalized.includes(term))) {
    return "list";
  }
  if (TOP1_SCOPE_TERMS.some((term) => normalized.includes(term))) {
    return "top_1";
  }
  return null;
}

function inferMetricFromBaseQuery(baseQuery: string): ClarificationMetric | null {
  const normalized = normalizeForFollowUp(baseQuery);
  if (METRIC_TERMS.revenue.some((term) => normalized.includes(term))) {
    return "revenue";
  }
  if (
    METRIC_TERMS.quantity.some((term) => normalized.includes(term)) ||
    normalized.includes("celkove prodeje") ||
    normalized.includes("total sales") ||
    normalized.includes("общие продажи")
  ) {
    return "quantity";
  }
  return null;
}

function inferScopeFromBaseQuery(baseQuery: string): ClarificationScope | null {
  const normalized = normalizeForFollowUp(baseQuery);
  if (PLURAL_PRODUCT_TERMS.some((term) => normalized.includes(term))) {
    return "list";
  }
  if (SINGULAR_PRODUCT_TERMS.some((term) => normalized.includes(term))) {
    return "top_1";
  }
  return null;
}

function canonicalLocale(locale: Locale): "cs" | "ru" | "en" {
  if (locale === "cs" || locale === "ru" || locale === "en") {
    return locale;
  }
  return "en";
}

function buildCanonicalClarificationQuery(
  locale: Locale,
  metric: ClarificationMetric,
  scope: ClarificationScope,
) {
  const resolvedLocale = canonicalLocale(locale);

  if (resolvedLocale === "cs") {
    if (scope === "list" && metric === "revenue") return "Jaké produkty mají nejvyšší tržby?";
    if (scope === "list" && metric === "quantity") return "Jaké produkty mají nejvyšší celkové prodeje?";
    if (scope === "top_1" && metric === "revenue") return "Který produkt má nejvyšší tržby?";
    return "Který produkt se prodává nejvíc?";
  }

  if (resolvedLocale === "ru") {
    if (scope === "list" && metric === "revenue") return "Какие продукты имеют самую высокую выручку?";
    if (scope === "list" && metric === "quantity") return "Какие продукты имеют наибольшие общие продажи?";
    if (scope === "top_1" && metric === "revenue") return "Какой продукт имеет самую высокую выручку?";
    return "Какой продукт продается больше всего?";
  }

  if (scope === "list" && metric === "revenue") return "Which products have the highest revenue?";
  if (scope === "list" && metric === "quantity") return "Which products have the highest total sales?";
  if (scope === "top_1" && metric === "revenue") return "Which product has the highest revenue?";
  return "Which product sells the most?";
}

function resolveClarificationFollowUp(
  pendingClarification: PendingClarificationContext,
  followUp: string,
  locale: Locale,
) {
  const missing = new Set(pendingClarification.clarification.missing);
  const metric = missing.has("metric")
    ? detectMetric(followUp)
    : inferMetricFromBaseQuery(pendingClarification.baseQuery);
  const scope = missing.has("scope")
    ? detectScope(followUp)
    : inferScopeFromBaseQuery(pendingClarification.baseQuery);

  if (!metric || !scope) {
    return null;
  }

  return buildCanonicalClarificationQuery(locale, metric, scope);
}

export function AssistantShell({ assistantType }: Props) {
  const { locale } = useLocale();
  const t = getT(locale).assistant;

  const [presets, setPresets] = useState<PresetQuestion[]>([]);
  const [accordionOpen, setAccordionOpen] = useState(false);
  const [customQuery, setCustomQuery] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [pendingClarification, setPendingClarification] = useState<PendingClarificationContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const title = assistantType === "knowledge" ? t.knowledgeTitle : t.analystTitle;
  const desc = assistantType === "knowledge" ? t.knowledgeDesc : t.analystDesc;

  useEffect(() => {
    fetchPresets(assistantType, locale)
      .then((res) => setPresets(res.questions))
      .catch(() => setPresets([]));
  }, [assistantType, locale]);

  useEffect(() => {
    setPendingClarification(null);
  }, [assistantType, locale]);

  function resetConversation() {
    setTurns([]);
    setError(null);
    setCustomQuery("");
    setPendingClarification(null);
    fetchPresets(assistantType, locale)
      .then((res) => setPresets(res.questions))
      .catch(() => setPresets([]));
  }

  function appendTurn(userQuery: string, requestQuery: string, answer: AssistantAnswer) {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    setTurns((current) => [
      ...current,
      {
        id,
        userQuery,
        requestQuery,
        answer,
        trace: null,
        traceOpen: false,
        traceLoading: false,
        traceError: null,
      },
    ]);
  }

  function updateTurn(turnId: string, patch: Partial<ConversationTurn>) {
    setTurns((current) =>
      current.map((turn) => (turn.id === turnId ? { ...turn, ...patch } : turn)),
    );
  }

  function shouldTreatAsClarificationFollowUp(input: string) {
    const normalized = input.trim().toLowerCase();
    if (!normalized) return false;
    if (normalized.includes("?")) return false;

    const tokens = normalized.split(/\s+/).filter(Boolean);
    if (tokens.length > 6) return false;

    const newQuestionStarts = new Set([
      "jaky",
      "jake",
      "ktery",
      "ktere",
      "kolik",
      "which",
      "what",
      "how",
      "who",
      "when",
      "where",
      "какой",
      "какие",
      "сколько",
      "как",
      "кто",
      "когда",
      "где",
    ]);

    return !newQuestionStarts.has(tokens[0]);
  }

  function syncPendingClarification(baseQuery: string, answer: AssistantAnswer) {
    if (answer.response_type === "clarification" && answer.clarification) {
      setPendingClarification({
        baseQuery,
        clarification: answer.clarification,
      });
    } else {
      setPendingClarification(null);
    }
  }

  async function askPreset(preset: PresetQuestion) {
    setAccordionOpen(false);
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAskPreset(assistantType, preset.id, locale);
      appendTurn(preset.text, preset.text, res);
      syncPendingClarification(preset.text, res);
      setCustomQuery("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function askCustom() {
    const typedQuery = customQuery.trim();
    if (!typedQuery) return;

    const useClarificationContext =
      pendingClarification !== null &&
      shouldTreatAsClarificationFollowUp(typedQuery);
    const resolvedFollowUpQuery =
      useClarificationContext && pendingClarification
        ? resolveClarificationFollowUp(pendingClarification, typedQuery, locale)
        : null;
    const requestQuery = resolvedFollowUpQuery ?? typedQuery;

    setLoading(true);
    setError(null);
    if (!useClarificationContext) {
      setPendingClarification(null);
    }

    try {
      const res = await fetchAskCustom(assistantType, requestQuery, locale);
      appendTurn(typedQuery, requestQuery, res);
      syncPendingClarification(
        useClarificationContext && pendingClarification
          ? pendingClarification.baseQuery
          : typedQuery,
        res,
      );
      setCustomQuery("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function toggleTrace(turnId: string) {
    const turn = turns.find((item) => item.id === turnId);
    if (!turn?.answer.trace_id) return;

    if (turn.traceOpen) {
      updateTurn(turnId, { traceOpen: false });
      return;
    }

    updateTurn(turnId, { traceOpen: true });
    if (turn.trace || turn.traceLoading) return;

    updateTurn(turnId, { traceLoading: true, traceError: null });
    try {
      const result = await fetchAssistantTrace(turn.answer.trace_id);
      updateTurn(turnId, { trace: result });
    } catch (e) {
      updateTurn(turnId, {
        traceError: e instanceof Error ? e.message : "Failed",
      });
    } finally {
      updateTurn(turnId, { traceLoading: false });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-emerald-400">{title}</h1>
          <p className="mt-1 text-slate-400">{desc}</p>
        </div>
        <button
          onClick={resetConversation}
          className="ml-4 mt-1 rounded border border-slate-600 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:border-emerald-500 hover:text-emerald-400"
          title={t.refresh}
        >
          ↺ {t.refresh}
        </button>
      </div>

      {presets.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/20">
          <button
            onClick={() => setAccordionOpen((open) => !open)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <span className="text-sm font-medium text-slate-300">
              {t.presetQuestions}
              <span className="ml-2 text-xs text-slate-500">({presets.length})</span>
            </span>
            <span
              className="text-slate-500 transition-transform"
              style={{ transform: accordionOpen ? "rotate(180deg)" : "none" }}
            >
              ▾
            </span>
          </button>

          {accordionOpen && (
            <div className="border-t border-slate-700">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  onClick={() => askPreset(preset)}
                  disabled={loading}
                  className="flex w-full items-center gap-2 border-b border-slate-800 px-4 py-2.5 text-left text-sm text-slate-300 transition-colors hover:bg-slate-700/50 hover:text-white last:border-b-0 disabled:opacity-50"
                >
                  <span className="shrink-0 text-xs text-emerald-500">▶</span>
                  {preset.text}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {pendingClarification && (
        <div className="rounded-lg border border-amber-700/60 bg-amber-950/20 px-4 py-3 text-sm text-amber-200">
          <div>{t.followUpHint}</div>
          <div className="mt-2 text-xs text-amber-300/80">
            {t.followUpBase}: <span className="italic">{pendingClarification.baseQuery}</span>
          </div>
          <button
            onClick={() => setPendingClarification(null)}
            className="mt-3 rounded border border-amber-700/70 px-2.5 py-1 text-xs text-amber-200 transition-colors hover:border-amber-500 hover:text-white"
          >
            {t.followUpClear}
          </button>
        </div>
      )}

      <div className="flex gap-3">
        <input
          ref={inputRef}
          value={customQuery}
          onChange={(e) => setCustomQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && askCustom()}
          placeholder={pendingClarification ? t.followUpHint : t.placeholder}
          className="flex-1 rounded border border-slate-600 bg-slate-900 px-4 py-2.5 text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
        />
        <button
          onClick={askCustom}
          disabled={loading || !customQuery.trim()}
          className="rounded bg-emerald-600 px-5 py-2.5 font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
        >
          {loading ? t.asking : t.ask}
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-900/20 px-4 py-3 text-sm text-red-400">
          {t.error}: {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-slate-400">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-400" />
          <span className="text-sm">{t.asking}</span>
        </div>
      )}

      {turns.length > 0 && (
        <div className="space-y-6">
          {turns.map((turn) => (
            <div key={turn.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-md border border-emerald-700/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                  {turn.userQuery}
                </div>
              </div>

              <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-5">
                <div className="flex flex-wrap items-center gap-2">
                  {turn.answer.query !== turn.userQuery && (
                    <p className="text-xs italic text-slate-500">{turn.answer.query}</p>
                  )}
                  {turn.answer.cached && (
                    <span className="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-400">
                      {t.cached}
                    </span>
                  )}
                  {turn.answer.response_type === "clarification" && (
                    <span className="rounded bg-amber-900/50 px-1.5 py-0.5 text-xs text-amber-200">
                      {t.clarification}
                    </span>
                  )}
                  {turn.answer.trace_id && (
                    <button
                      onClick={() => toggleTrace(turn.id)}
                      className="rounded border border-slate-700 px-1.5 py-0.5 text-xs text-slate-400 transition-colors hover:border-emerald-500 hover:text-emerald-300"
                    >
                      {turn.traceOpen ? t.traceHide : t.traceShow}
                    </button>
                  )}
                </div>

                {turn.answer.trace_summary && (
                  <div className="mt-3 rounded border border-slate-700 bg-slate-900/40 px-3 py-2 text-xs text-slate-400">
                    <div>
                      {t.traceId}: <span className="font-mono text-slate-300">{turn.answer.trace_summary.trace_id}</span>
                    </div>
                    <div>
                      {t.traceStatus}: <span className="text-slate-300">{turn.answer.trace_summary.status}</span>
                    </div>
                    <div>
                      {t.traceSource}: <span className="text-slate-300">{turn.answer.trace_summary.cache_source || "-"}</span>
                    </div>
                    <div>
                      {t.traceStrategy}: <span className="text-slate-300">{turn.answer.trace_summary.cache_strategy || "-"}</span>
                    </div>
                    <div>
                      {t.traceSimilarity}: <span className="text-slate-300">{turn.answer.trace_summary.similarity?.toFixed(3) ?? "-"}</span>
                    </div>
                    <div>
                      {t.traceLatency}: <span className="text-slate-300">{turn.answer.trace_summary.total_latency_ms ?? "-"} ms</span>
                    </div>
                  </div>
                )}

                <p className="mt-3 whitespace-pre-wrap leading-relaxed text-slate-200">
                  {turn.answer.answer || t.noAnswer}
                </p>

                {turn.answer.used_tools.length > 0 && (
                  <div className="border-t border-slate-700 pt-3">
                    <p className="mb-1 text-xs font-medium text-slate-400">{t.tools}</p>
                    <div className="flex flex-wrap gap-1">
                      {turn.answer.used_tools.map((tool, index) => (
                        <span
                          key={`${turn.id}-tool-${index}`}
                          className="rounded bg-slate-700 px-2 py-0.5 text-xs text-slate-300"
                        >
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {turn.answer.citations.length > 0 && (
                  <div className="border-t border-slate-700 pt-3">
                    <p className="mb-2 text-xs font-medium text-slate-400">{t.sources}</p>
                    <ul className="space-y-1">
                      {turn.answer.citations.map((citation, index) => (
                        <li
                          key={`${turn.id}-citation-${index}`}
                          className="rounded border border-slate-700 bg-slate-900/50 px-3 py-1.5 text-xs text-slate-400"
                        >
                          <span className="font-medium text-slate-300">{citation.source}</span>
                          {citation.excerpt && (
                            <span className="ml-2 text-slate-500">— {citation.excerpt.slice(0, 100)}…</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {turn.traceOpen && (
                  <div className="border-t border-slate-700 pt-3">
                    <p className="mb-2 text-xs font-medium text-slate-400">{t.traceDetails}</p>
                    {turn.traceLoading && <p className="text-xs text-slate-500">{t.traceLoading}</p>}
                    {turn.traceError && (
                      <p className="text-xs text-red-400">
                        {t.traceUnavailable}: {turn.traceError}
                      </p>
                    )}
                    {turn.trace && (
                      <div className="space-y-2">
                        {turn.trace.steps.map((step) => (
                          <div
                            key={`${turn.id}-step-${step.step_index}`}
                            className="rounded border border-slate-700 bg-slate-900/50 p-3"
                          >
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="font-mono text-emerald-400">#{step.step_index}</span>
                              <span className="text-slate-200">{step.step_name}</span>
                              <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">
                                {step.status}
                              </span>
                              {step.latency_ms != null && (
                                <span className="text-slate-500">{step.latency_ms} ms</span>
                              )}
                            </div>
                            {step.payload && (
                              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-slate-950/80 p-3 text-[11px] text-slate-400">
                                {JSON.stringify(step.payload, null, 2)}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
