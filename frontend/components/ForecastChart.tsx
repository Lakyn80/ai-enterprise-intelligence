"use client";

import type { ForecastResponse } from "@/lib/types";

export function ForecastChart({ data }: { data: ForecastResponse }) {
  if (!data.points.length)
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-8 text-center text-slate-400">
        No forecast data. Load data and train the model first.
      </div>
    );

  const maxQty = Math.max(...data.points.map((p) => p.predicted_quantity));
  const minQty = Math.min(...data.points.map((p) => p.predicted_quantity));
  const range = maxQty - minQty || 1;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
      <h2 className="mb-4 font-semibold text-white">Forecast: {data.product_id}</h2>
      <div
        className="flex items-end gap-1"
        style={{ height: 200 }}
      >
        {data.points.map((p) => {
          const h = ((p.predicted_quantity - minQty) / range) * 150 + 20;
          return (
            <div
              key={p.date}
              className="flex-1 rounded-t bg-emerald-600/80 transition hover:bg-emerald-500"
              style={{ height: h }}
              title={`${p.date}: ${p.predicted_quantity.toFixed(1)}`}
            />
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-500">
        <span>{data.points[0]?.date}</span>
        <span>{data.points[data.points.length - 1]?.date}</span>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-600 text-left text-slate-400">
              <th className="p-2">Date</th>
              <th className="p-2">Quantity</th>
              <th className="p-2">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {data.points.slice(0, 14).map((p) => (
              <tr key={p.date} className="border-b border-slate-700/50">
                <td className="p-2">{p.date}</td>
                <td className="p-2">{p.predicted_quantity.toFixed(1)}</td>
                <td className="p-2">{p.predicted_revenue?.toFixed(2) ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
