"use client";

import { useState } from "react";
import { seedData, trainModel } from "@/lib/api";
import type { TrainResult } from "@/lib/types";

export default function AdminPage() {
  const [apiKey, setApiKey] = useState("");

  // Seed state
  const [seedLoading, setSeedLoading] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  // Train state – empty = auto-detect (backend uses max available, capped at 3 years)
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [splitDate, setSplitDate] = useState("");
  const [trainLoading, setTrainLoading] = useState(false);
  const [trainResult, setTrainResult] = useState<TrainResult | null>(null);
  const [trainError, setTrainError] = useState<string | null>(null);

  async function handleSeed() {
    setSeedLoading(true);
    setSeedResult(null);
    setSeedError(null);
    try {
      const res = await seedData(apiKey);
      setSeedResult(res.message);
    } catch (e) {
      setSeedError(e instanceof Error ? e.message : "Chyba");
    } finally {
      setSeedLoading(false);
    }
  }

  async function handleTrain() {
    setTrainLoading(true);
    setTrainResult(null);
    setTrainError(null);
    try {
      const res = await trainModel(fromDate, toDate, apiKey, splitDate || undefined);
      setTrainResult(res);
    } catch (e) {
      setTrainError(e instanceof Error ? e.message : "Chyba");
    } finally {
      setTrainLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">Admin</h1>

      {/* API Key */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <label className="block text-sm font-medium text-slate-400">API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="dev-admin-key-change-in-production"
          className="mt-1 w-full max-w-sm rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
        />
      </div>

      {/* Seed demo data */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
        <h2 className="mb-1 text-lg font-semibold text-white">1. Seed demo dat</h2>
        <p className="mb-4 text-sm text-slate-400">
          Vytvoří 120 dní historických dat pro produkty P001, P002, P003. Přeskočí, pokud data už existují.
        </p>
        <button
          onClick={handleSeed}
          disabled={seedLoading || !apiKey}
          className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {seedLoading ? "Seeduji..." : "Seed data"}
        </button>
        {seedResult && (
          <p className="mt-3 text-sm text-emerald-400">{seedResult}</p>
        )}
        {seedError && (
          <p className="mt-3 text-sm text-red-400">{seedError}</p>
        )}
      </div>

      {/* Train model */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/30 p-6">
        <h2 className="mb-1 text-lg font-semibold text-white">2. Trénink modelu</h2>
        <p className="mb-4 text-sm text-slate-400">
          Natrénuje LightGBM model na historických datech. Volitelně nastav{" "}
          <span className="text-slate-300">split_date</span> pro out-of-sample evaluaci (model se trénuje
          pouze na datech před split_date, metriky se počítají na zbytku).
        </p>
        <p className="mb-4 rounded border border-slate-700 bg-slate-900/50 px-3 py-2 text-xs text-slate-400">
          <span className="text-emerald-400">Od / Do: ponech prázdné</span> — backend automaticky zvolí
          maximálně dostupný rozsah, max. 3 roky zpět od posledního záznamu v DB.
        </p>

        <div className="flex flex-wrap gap-4">
          <div>
            <label className="block text-sm text-slate-400">
              Od <span className="text-slate-500">(prázdné = auto)</span>
            </label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400">
              Do <span className="text-slate-500">(prázdné = auto)</span>
            </label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400">
              Split date{" "}
              <span className="text-slate-500">(volitelné)</span>
            </label>
            <input
              type="date"
              value={splitDate}
              onChange={(e) => setSplitDate(e.target.value)}
              className="mt-1 rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={handleTrain}
              disabled={trainLoading || !apiKey}
              className="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              {trainLoading ? "Trénuji..." : "Spustit trénink"}
            </button>
          </div>
        </div>

        {trainError && (
          <div className="mt-4 rounded border border-red-800 bg-red-950/50 p-3 text-sm text-red-300">
            {trainError}
          </div>
        )}

        {trainResult && (
          <div className="mt-4 rounded-lg border border-emerald-800 bg-emerald-950/30 p-4">
            <p className="mb-2 text-sm font-medium text-emerald-400">
              Model natrénován &nbsp;·&nbsp; verze {trainResult.version}
            </p>
            <div className="flex flex-wrap gap-6 text-sm text-slate-300">
              <span>
                MAE: <span className="font-mono text-white">{trainResult.mae.toFixed(3)}</span>
              </span>
              <span>
                RMSE: <span className="font-mono text-white">{trainResult.rmse.toFixed(3)}</span>
              </span>
              <span>
                MAPE: <span className="font-mono text-white">{trainResult.mape.toFixed(1)}%</span>
              </span>
              <span className="text-slate-500">
                n={trainResult.n_eval_samples} ({trainResult.eval_source})
              </span>
            </div>
            {trainResult.date_range && (
              <p className="mt-2 text-xs text-slate-500">
                train {trainResult.date_range.train_start} → {trainResult.date_range.train_end}
                &nbsp;|&nbsp;
                test {trainResult.date_range.test_start} → {trainResult.date_range.test_end}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
