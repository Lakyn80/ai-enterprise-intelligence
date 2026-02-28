"use client";

import { useState } from "react";
import { ForecastChart } from "@/components/ForecastChart";
import { ScenarioForm } from "@/components/ScenarioForm";
import { fetchForecast } from "@/lib/api";
import type { ForecastResponse } from "@/lib/types";

export default function ForecastPage() {
  const [productId, setProductId] = useState("P001");
  const [fromDate, setFromDate] = useState(
    () => new Date().toISOString().slice(0, 10)
  );
  const [toDate, setToDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().slice(0, 10);
  });
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadForecast() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchForecast(productId, fromDate, toDate);
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load forecast");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">Forecast Dashboard</h1>

      <div className="flex flex-wrap gap-4 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <div>
          <label className="block text-sm text-slate-400">Product ID</label>
          <input
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="mt-1 w-32 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400">From</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400">To</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={loadForecast}
            disabled={loading}
            className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Load Forecast"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 p-4 text-red-300">
          {error}
        </div>
      )}

      {data && (
        <>
          <ForecastChart data={data} />
          <ScenarioForm
            productId={productId}
            fromDate={fromDate}
            toDate={toDate}
          />
        </>
      )}
    </div>
  );
}
