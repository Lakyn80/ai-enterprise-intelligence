"use client";

import { useEffect, useState } from "react";
import { ForecastChart } from "@/components/ForecastChart";
import { ScenarioForm } from "@/components/ScenarioForm";
import { fetchForecast, fetchProducts, fetchBacktest } from "@/lib/api";
import type { ForecastResponse } from "@/lib/types";

export default function ForecastPage() {
  const [products, setProducts] = useState<string[]>([]);
  const [productId, setProductId] = useState("P001");
  const [fromDate, setFromDate] = useState("2023-06-01");
  const [toDate, setToDate] = useState("2023-06-30");
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backtest, setBacktest] = useState<{ mae?: number; mape?: number; n_predictions?: number; message?: string } | null>(null);

  useEffect(() => {
    fetchProducts()
      .then((p) => {
        const withAliases = ["P001", "P002", "P003", ...p.filter((x) => !["P0001", "P0002", "P0003"].includes(x))];
        setProducts(withAliases.length > 0 ? withAliases : p);
        if (p.length > 0 && !p.includes(productId) && !["P001", "P002", "P003"].includes(productId))
          setProductId("P001");
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (products.length > 0 && productId) {
      setLoading(true);
      setError(null);
      setBacktest(null);
      fetchForecast(productId, fromDate, toDate)
        .then((res) => setData(res))
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to load forecast"))
        .finally(() => setLoading(false));
      fetchBacktest(productId, fromDate, toDate).then(setBacktest).catch(() => setBacktest({ message: "Backtest není dostupný (potřeba historická data)" }));
    }
  }, [products.length, productId, fromDate, toDate]);

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
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="mt-1 w-32 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
          >
            {products.length > 0 ? (
              products.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))
            ) : (
              <option value={productId}>{productId}</option>
            )}
          </select>
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

      {backtest && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-4">
          <h2 className="mb-2 font-semibold text-white">Backtest – přesnost modelu vs. skutečnost</h2>
          {backtest.mae != null ? (
            <p className="text-slate-300">
              MAE: {backtest.mae.toFixed(1)} | MAPE: {backtest.mape?.toFixed(1)}% | predikcí: {backtest.n_predictions ?? "-"}
            </p>
          ) : (
            <p className="text-slate-400">{backtest.message}</p>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Pro historická data (např. 2023-06-01 až 2023-06-30) porovná predikce s reálnými prodeji.
          </p>
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
