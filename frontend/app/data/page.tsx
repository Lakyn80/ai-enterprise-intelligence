"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { fetchHistoricalData, fetchProducts } from "@/lib/api";
import { useLocale } from "@/lib/i18n/LocaleContext";
import { getT } from "@/lib/i18n/translations";

const LineChart = dynamic(() => import("recharts").then((m) => m.LineChart), { ssr: false });
const BarChart = dynamic(() => import("recharts").then((m) => m.BarChart), { ssr: false });
const Line = dynamic(() => import("recharts").then((m) => m.Line), { ssr: false });
const Bar = dynamic(() => import("recharts").then((m) => m.Bar), { ssr: false });
const XAxis = dynamic(() => import("recharts").then((m) => m.XAxis), { ssr: false });
const YAxis = dynamic(() => import("recharts").then((m) => m.YAxis), { ssr: false });
const CartesianGrid = dynamic(() => import("recharts").then((m) => m.CartesianGrid), { ssr: false });
const Tooltip = dynamic(() => import("recharts").then((m) => m.Tooltip), { ssr: false });
const Legend = dynamic(() => import("recharts").then((m) => m.Legend), { ssr: false });
const ResponsiveContainer = dynamic(() => import("recharts").then((m) => m.ResponsiveContainer), { ssr: false });

interface DataPoint {
  date: string;
  product_id: string;
  quantity: number;
  revenue: number;
  price: number;
}

export default function DataPage() {
  const { locale } = useLocale();
  const t = getT(locale).data;
  const [products, setProducts] = useState<string[]>([]);
  const [productId, setProductId] = useState<string>("");
  const [fromDate, setFromDate] = useState("2022-01-01");
  const [toDate, setToDate] = useState("2022-06-30");
  const [data, setData] = useState<DataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    try {
      const list = await fetchProducts();
      setProducts(list);
      if (list.length > 0 && !productId) setProductId(list[0]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load products");
    }
  }, [productId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchHistoricalData(fromDate, toDate, productId || undefined);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, productId]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    if (products.length > 0) loadData();
  }, [loadData, products.length]);

  const chartData = data.reduce((acc: Record<string, { date: string; quantity: number; revenue: number; count: number }>, row) => {
    const k = row.date;
    if (!acc[k]) acc[k] = { date: k, quantity: 0, revenue: 0, count: 0 };
    acc[k].quantity += row.quantity;
    acc[k].revenue += row.revenue;
    acc[k].count += 1;
    return acc;
  }, {});
  const series = Object.values(chartData).sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">{t.title}</h1>
      <p className="text-slate-400">{t.desc}</p>

      <div className="flex flex-wrap gap-4 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <div>
          <label className="block text-sm text-slate-400">{t.product}</label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white"
          >
            <option value="">{t.allProducts}</option>
            {products.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-slate-400">{t.from}</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="block text-sm text-slate-400">{t.to}</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={loadData}
            disabled={loading}
            className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {loading ? t.loading : t.load}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/50 p-4 text-red-300">
          {error}
        </div>
      )}

      {series.length > 0 && (
        <>
          <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
            <h2 className="mb-4 font-semibold text-white">{t.chartQty}</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
                <YAxis stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #475569" }}
                  labelStyle={{ color: "#f1f5f9" }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="quantity"
                  stroke="#10b981"
                  strokeWidth={2}
                  name={t.qty}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
            <h2 className="mb-4 font-semibold text-white">{t.chartRevenue}</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
                <YAxis stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #475569" }}
                />
                <Legend />
                <Bar dataKey="revenue" fill="#10b981" name={t.revenue} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {products.length === 0 && !loading && !error && (
        <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-6 text-amber-200">
          <p className="font-medium">{t.noData}</p>
          <p className="mt-2 text-sm">
            {t.noDataHint}{" "}
            <code className="rounded bg-slate-800 px-2 py-1">
              curl -X POST http://localhost:8000/api/admin/import-kaggle -H &quot;X-Api-Key: ...&quot;
            </code>
          </p>
        </div>
      )}
    </div>
  );
}
