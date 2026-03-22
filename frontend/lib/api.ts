import type { BacktestResult, TrainResult } from "./types";

const API_BASE =
  typeof window === "undefined"
    ? process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"  // server-side: need absolute URL
    : process.env.NEXT_PUBLIC_API_URL || "";  // client-side: relative URL → nginx proxies /api/ to backend

export async function fetchForecast(
  productId: string,
  fromDate: string,
  toDate: string
) {
  const params = new URLSearchParams({
    product_id: productId,
    from_date: fromDate,
    to_date: toDate,
  });
  const r = await fetch(`${API_BASE}/api/forecast?${params}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchScenario(
  productId: string,
  fromDate: string,
  toDate: string,
  priceDeltaPct: number
) {
  const r = await fetch(`${API_BASE}/api/scenario/price-change`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_id: productId,
      from_date: fromDate,
      to_date: toDate,
      price_delta_pct: priceDeltaPct,
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchProducts(): Promise<string[]> {
  const r = await fetch(`${API_BASE}/api/data/products`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchBacktest(
  productId: string,
  fromDate: string,
  toDate: string,
  trainWindowDays = 90,
  stepDays = 7
): Promise<BacktestResult> {
  const params = new URLSearchParams({
    product_id: productId,
    from_date: fromDate,
    to_date: toDate,
    train_window_days: String(trainWindowDays),
    step_days: String(stepDays),
  });
  const r = await fetch(`${API_BASE}/api/backtest?${params}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchHistoricalData(
  fromDate: string,
  toDate: string,
  productId?: string
) {
  const params = new URLSearchParams({
    from_date: fromDate,
    to_date: toDate,
  });
  if (productId) params.set("product_id", productId);
  const r = await fetch(`${API_BASE}/api/data/historical?${params}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function trainModel(
  fromDate: string | undefined,
  toDate: string | undefined,
  apiKey: string,
  splitDate?: string
): Promise<TrainResult> {
  const params = new URLSearchParams();
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  if (splitDate) params.set("split_date", splitDate);
  const r = await fetch(`${API_BASE}/api/admin/train?${params}`, {
    method: "POST",
    headers: { "X-Api-Key": apiKey },
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function seedData(apiKey: string): Promise<{ status: string; message: string; rows: number }> {
  const r = await fetch(`${API_BASE}/api/admin/seed`, {
    method: "POST",
    headers: { "X-Api-Key": apiKey },
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchChat(
  message: string,
  provider: "openai" | "deepseek" = "deepseek"
) {
  const r = await fetch(`${API_BASE}/api/assistant/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, provider }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchKnowledgeQuery(query: string) {
  const r = await fetch(`${API_BASE}/api/knowledge/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ---------------------------------------------------------------------------
// New Assistants API
// ---------------------------------------------------------------------------

export type AssistantType = "knowledge" | "analyst";
export type Locale = "en" | "cs" | "sk" | "ru";

export interface PresetQuestion {
  id: string;
  text: string;
}

export interface PresetsResponse {
  assistant_type: AssistantType;
  locale: Locale;
  questions: PresetQuestion[];
}

export interface Citation {
  source: string;
  excerpt?: string;
}

export interface ClarificationMessage {
  cs: string;
  ru: string;
  en: string;
}

export interface Clarification {
  type: "clarification";
  missing: string[];
  message: ClarificationMessage;
}

export interface AssistantAnswer {
  question_id: string | null;
  query: string;
  answer: string;
  locale: Locale;
  response_type?: "answer" | "clarification";
  clarification?: Clarification | null;
  cached: boolean;
  citations: Citation[];
  used_tools: string[];
  trace_id?: string | null;
  trace_summary?: AssistantTraceSummary | null;
}

export interface AssistantTraceSummary {
  trace_id: string;
  status: string;
  request_kind: "preset" | "custom";
  cached: boolean;
  cache_source?: string | null;
  cache_strategy?: string | null;
  similarity?: number | null;
  total_latency_ms?: number | null;
}

export interface AssistantTraceStep {
  step_index: number;
  step_name: string;
  status: string;
  latency_ms?: number | null;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface AssistantTrace extends AssistantTraceSummary {
  assistant_type: AssistantType;
  locale: Locale;
  question_id?: string | null;
  user_query: string;
  normalized_query: string;
  answer?: string | null;
  error?: string | null;
  created_at: string;
  completed_at?: string | null;
  steps: AssistantTraceStep[];
}

export async function fetchPresets(
  assistantType: AssistantType,
  locale: Locale = "en"
): Promise<PresetsResponse> {
  const r = await fetch(
    `${API_BASE}/api/assistants/${assistantType}/presets?locale=${locale}`
  );
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchAskPreset(
  assistantType: AssistantType,
  questionId: string,
  locale: Locale = "en"
): Promise<AssistantAnswer> {
  const r = await fetch(`${API_BASE}/api/assistants/ask-preset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      assistant_type: assistantType,
      question_id: questionId,
      locale,
    }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchAskCustom(
  assistantType: AssistantType,
  query: string,
  locale: Locale = "en"
): Promise<AssistantAnswer> {
  const r = await fetch(`${API_BASE}/api/assistants/ask-custom`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ assistant_type: assistantType, query, locale }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function fetchAssistantTrace(traceId: string): Promise<AssistantTrace> {
  const r = await fetch(`${API_BASE}/api/assistants/traces/${traceId}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
