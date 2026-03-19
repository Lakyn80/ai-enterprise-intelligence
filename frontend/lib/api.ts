import type { BacktestResult, TrainResult } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
