"use client";

import { useEffect, useState } from "react";
import { ForecastChart } from "@/components/ForecastChart";
import { ScenarioForm } from "@/components/ScenarioForm";
import { fetchForecast, fetchProducts, fetchBacktest, fetchHistoricalData } from "@/lib/api";
import type { BacktestResult, ForecastResponse } from "@/lib/types";

interface ActualPoint {
  date: string;
  quantity: number;
}

export default function ForecastPage() {
  const [products, setProducts] = useState<string[]>([]);
  const [productId, setProductId] = useState("");
  const [fromDate, setFromDate] = useState("2023-06-01");
  const [toDate, setToDate] = useState("2023-06-30");
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [actuals, setActuals] = useState<ActualPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);

  useEffect(() => {
    fetchProducts()
      .then((p) => {
        setProducts(p);
        if (p.length > 0) setProductId(p[0]);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (products.length > 0 && productId) {
      setLoading(true);
      setError(null);
      setBacktest(null);
      setActuals([]);

      Promise.all([
        fetchForecast(productId, fromDate, toDate),
        // Load actuals for the same range to enable predicted vs real comparison
        fetchHistoricalData(fromDate, toDate, productId).catch(() => []),
      ])
        .then(([forecast, historical]) => {
          setData(forecast);
          // Aggregate historical by date (sum quantity across rows for the product)
          const byDate: Record<string, number> = {};
          for (const row of historical as { date: string; quantity: number }[]) {
            byDate[row.date] = (byDate[row.date] ?? 0) + row.quantity;
          }
          setActuals(Object.entries(byDate).map(([date, quantity]) => ({ date, quantity })));
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to load forecast"))
        .finally(() => setLoading(false));

      // Use a 6-month window ending at toDate so the backtest has enough
      // rolling windows (~150+ samples) to give representative MAPE.
      // Using only the forecast window (e.g. 1 month) yields n≈28 and
      // unreliable high-variance metrics that don't reflect true model quality.
      const backtestTo = new Date(toDate);
      const backtestFrom = new Date(backtestTo);
      backtestFrom.setMonth(backtestFrom.getMonth() - 6);
      const backtestFromStr = backtestFrom.toISOString().split("T")[0];

      fetchBacktest(productId, backtestFromStr, toDate)
        .then(setBacktest)
        .catch(() =>
          setBacktest({
            mae: null,
            rmse: null,
            mape: null,
            n_samples: 0,
            message: "Backtest není dostupný (potřeba historická data)",
          })
        );
    }
  }, [products.length, productId, fromDate, toDate]);

  async function loadForecast() {
    setLoading(true);
    setError(null);
    setActuals([]);
    try {
      const [forecast, historical] = await Promise.all([
        fetchForecast(productId, fromDate, toDate),
        fetchHistoricalData(fromDate, toDate, productId).catch(() => []),
      ]);
      setData(forecast);
      const byDate: Record<string, number> = {};
      for (const row of historical as { date: string; quantity: number }[]) {
        byDate[row.date] = (byDate[row.date] ?? 0) + row.quantity;
      }
      setActuals(Object.entries(byDate).map(([date, quantity]) => ({ date, quantity })));
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
            <div className="flex flex-wrap gap-6 text-slate-300">
              <span>MAE: <span className="font-mono text-white">{backtest.mae.toFixed(2)}</span></span>
              <span>RMSE: <span className="font-mono text-white">{backtest.rmse?.toFixed(2) ?? "–"}</span></span>
              <span>MAPE: <span className="font-mono text-white">{backtest.mape?.toFixed(1)}%</span></span>
              <span className="text-slate-500">n={backtest.n_samples}</span>
            </div>
          ) : (
            <p className="text-slate-400">{backtest.message}</p>
          )}
          {backtest.date_range && (
            <p className="mt-1 text-xs text-slate-500">
              train {backtest.date_range.train_start} → {backtest.date_range.train_end} &nbsp;|&nbsp;
              test {backtest.date_range.test_start} → {backtest.date_range.test_end}
            </p>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Porovná predikce s reálnými prodeji na historickém rozsahu dat.
          </p>
        </div>
      )}

      {data && (
        <>
          <ForecastChart data={data} actuals={actuals.length > 0 ? actuals : undefined} />
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
