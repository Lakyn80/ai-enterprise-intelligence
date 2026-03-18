"use client";

import type { ForecastResponse } from "@/lib/types";

interface ActualPoint {
  date: string;
  quantity: number;
}

interface Props {
  data: ForecastResponse;
  actuals?: ActualPoint[];
}

export function ForecastChart({ data, actuals }: Props) {
  if (!data.points.length)
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-8 text-center text-slate-400">
        No forecast data. Load data and train the model first.
      </div>
    );

  // Build merged series: predicted + actual (if available) keyed by date
  const actualsMap = new Map((actuals ?? []).map((a) => [a.date, a.quantity]));
  const hasActuals = actualsMap.size > 0;

  const allQty = [
    ...data.points.map((p) => p.predicted_quantity),
    ...(actuals ?? []).map((a) => a.quantity),
  ];
  const maxQty = Math.max(...allQty);
  const minQty = Math.min(...allQty);
  const range = maxQty - minQty || 1;
  const BAR_H = 160;

  const toH = (v: number) => ((v - minQty) / range) * BAR_H + 10;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-white">Forecast: {data.product_id}</h2>
        {hasActuals && (
          <div className="flex gap-4 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-4 rounded bg-emerald-600" /> Predikce
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-4 rounded bg-amber-400/70" /> Skutečnost
            </span>
          </div>
        )}
      </div>

      {/* Chart */}
      <div className="relative overflow-x-auto">
        <div
          className="flex items-end gap-px"
          style={{ height: BAR_H + 20, minWidth: data.points.length * 8 }}
        >
          {data.points.map((p) => {
            const actual = actualsMap.get(p.date);
            const predH = toH(p.predicted_quantity);
            const actH = actual != null ? toH(actual) : null;
            const diff =
              actual != null
                ? (((p.predicted_quantity - actual) / (actual + 1e-8)) * 100).toFixed(1)
                : null;

            return (
              <div
                key={p.date}
                className="relative flex flex-1 items-end justify-center"
                style={{ minWidth: 6, height: BAR_H + 20 }}
                title={
                  actual != null
                    ? `${p.date}\nPredikce: ${p.predicted_quantity.toFixed(1)}\nSkutečnost: ${actual.toFixed(1)}\nChyba: ${diff}%`
                    : `${p.date}: ${p.predicted_quantity.toFixed(1)}`
                }
              >
                {/* Actual bar (behind) */}
                {actH != null && (
                  <div
                    className="absolute bottom-0 w-full rounded-t bg-amber-400/50"
                    style={{ height: actH }}
                  />
                )}
                {/* Predicted bar (in front) */}
                <div
                  className="absolute bottom-0 w-3/5 rounded-t bg-emerald-600/80 transition hover:bg-emerald-500"
                  style={{ height: predH }}
                />
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex justify-between text-xs text-slate-500">
          <span>{data.points[0]?.date}</span>
          <span>{data.points[data.points.length - 1]?.date}</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-600 text-left text-slate-400">
              <th className="p-2">Datum</th>
              <th className="p-2">Predikce</th>
              {hasActuals && <th className="p-2">Skutečnost</th>}
              {hasActuals && <th className="p-2">Chyba %</th>}
              <th className="p-2">Tržby (pred.)</th>
            </tr>
          </thead>
          <tbody>
            {data.points.slice(0, 30).map((p) => {
              const actual = actualsMap.get(p.date);
              const errPct =
                actual != null
                  ? (((p.predicted_quantity - actual) / (actual + 1e-8)) * 100).toFixed(1)
                  : null;
              const isOver = errPct != null && parseFloat(errPct) > 0;
              return (
                <tr key={p.date} className="border-b border-slate-700/50">
                  <td className="p-2 text-slate-400">{p.date}</td>
                  <td className="p-2 font-mono">{p.predicted_quantity.toFixed(1)}</td>
                  {hasActuals && (
                    <td className="p-2 font-mono text-amber-300">
                      {actual != null ? actual.toFixed(1) : "–"}
                    </td>
                  )}
                  {hasActuals && (
                    <td
                      className={`p-2 font-mono text-xs ${
                        errPct == null
                          ? "text-slate-500"
                          : isOver
                          ? "text-red-400"
                          : "text-emerald-400"
                      }`}
                    >
                      {errPct != null ? `${isOver ? "+" : ""}${errPct}%` : "–"}
                    </td>
                  )}
                  <td className="p-2">{p.predicted_revenue?.toFixed(2) ?? "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
