"use client";

import { useState } from "react";
import { fetchScenario } from "@/lib/api";
import type { ScenarioResponse } from "@/lib/types";

interface ScenarioFormProps {
  productId: string;
  fromDate: string;
  toDate: string;
}

export function ScenarioForm({ productId, fromDate, toDate }: ScenarioFormProps) {
  const [priceDelta, setPriceDelta] = useState(5);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runScenario() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchScenario(
        productId,
        fromDate,
        toDate,
        priceDelta
      );
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-800/30 p-6">
      <h2 className="font-semibold text-white">Price Change Scenario</h2>
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-sm text-slate-400">Price change (%)</label>
          <input
            type="number"
            value={priceDelta}
            onChange={(e) => setPriceDelta(Number(e.target.value))}
            className="mt-1 w-24 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white"
          />
        </div>
        <button
          onClick={runScenario}
          disabled={loading}
          className="rounded bg-amber-600 px-4 py-2 font-medium text-white hover:bg-amber-500 disabled:opacity-50"
        >
          {loading ? "Computing..." : "Compare +5%"}
        </button>
      </div>
      {error && (
        <div className="text-sm text-red-400">{error}</div>
      )}
      {result && (
        <div className="rounded border border-slate-600 bg-slate-900/50 p-4">
          <p className="text-slate-300">
            Price {result.price_delta_pct > 0 ? "+" : ""}
            {result.price_delta_pct}%: Revenue{" "}
            {result.delta_revenue_pct != null
              ? `${result.delta_revenue_pct >= 0 ? "+" : ""}${result.delta_revenue_pct.toFixed(1)}%`
              : "N/A"}
            , Quantity{" "}
            {result.delta_quantity_pct != null
              ? `${result.delta_quantity_pct >= 0 ? "+" : ""}${result.delta_quantity_pct.toFixed(1)}%`
              : "N/A"}
          </p>
        </div>
      )}
    </div>
  );
}
