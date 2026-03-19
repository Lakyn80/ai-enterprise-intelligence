"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchHistoricalData, fetchProducts } from "@/lib/api";
import { useLocale } from "@/lib/i18n/LocaleContext";
import { getT } from "@/lib/i18n/translations";

interface DataPoint {
  date: string;
  product_id: string;
  quantity: number;
  revenue: number;
  price: number;
}

interface ChartPoint {
  date: string;
  quantity: number;
  revenue: number;
  count: number;
}

function Charts({ series, qty, revenue }: { series: ChartPoint[]; qty: string; revenue: string }) {
  const [RC, setRC] = useState<typeof import("recharts") | null>(null);

  useEffect(() => {
    import("recharts").then(setRC);
  }, []);

  if (!RC || series.length === 0) return null;
  const { ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } = RC;

  return (
    <>
      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
        <h2 className="mb-4 font-semibold text-white">{qty}</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="date" stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
            <YAxis stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
            <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #475569" }} labelStyle={{ color: "#f1f5f9" }} />
            <Legend />
            <Line type="monotone" dataKey="quantity" stroke="#10b981" strokeWidth={2} name={qty} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
        <h2 className="mb-4 font-semibold text-white">{revenue}</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="date" stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
            <YAxis stroke="#94a3b8" tick={{ fill: "#94a3b8" }} />
            <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #475569" }} />
            <Legend />
            <Bar dataKey="revenue" fill="#10b981" name={revenue} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
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

  useEffect(() => { loadProducts(); }, [loadProducts]);
  useEffect(() => { if (products.length > 0) loadData(); }, [loadData, products.length]);

  const chartData = data.reduce((acc: Record<string, ChartPoint>, row) => {
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
          <select value={productId} onChange={(e) => setProductId(e.target.value)} className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white">
            <option value="">{t.allProducts}</option>
            {products.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm text-slate-400">{t.from}</label>
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white" />
        </div>
        <div>
          <label className="block text-sm text-slate-400">{t.to}</label>
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white" />
        </div>
        <div className="flex items-end">
          <button onClick={loadData} disabled={loading} className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
            {loading ? t.loading : t.load}
          </button>
        </div>
      </div>

      {error && <div className="rounded border border-red-800 bg-red-950/50 p-4 text-red-300">{error}</div>}

      <Charts series={series} qty={t.chartQty} revenue={t.chartRevenue} />

      {products.length === 0 && !loading && !error && (
        <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-6 text-amber-200">
          <p className="font-medium">{t.noData}</p>
          <p className="mt-2 text-sm">{t.noDataHint}{" "}<code className="rounded bg-slate-800 px-2 py-1">curl -X POST http://localhost:8000/api/admin/import-kaggle -H &quot;X-Api-Key: ...&quot;</code></p>
        </div>
      )}
    </div>
  );
}
