"""
End-to-end backtesting demo – spust: python scripts/demo_backtest.py
"""
import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://x:x@localhost/x")
os.environ.setdefault("API_KEY_ADMIN", "x")
os.environ.setdefault("RAG_ENABLED", "false")

import numpy as np
import pandas as pd
import tempfile
import shutil
from datetime import date, timedelta

from app.forecasting.backtest import (
    time_based_split_by_date,
    evaluate_time_split,
    rolling_backtest,
    backtest_metrics,
    _compute_test_features_with_context,
)
from app.forecasting.training import train_model, predict, DATE_COL, ENTITY_COL, TARGET_COL

SEP = "=" * 60


def banner(title):
    print()
    print(SEP)
    print(title)
    print(SEP)


# ── 1. DATA ─────────────────────────────────────────────────────────────────
banner("KROK 1 -- Generovani 120 dni dat (3 produkty)")

np.random.seed(42)
rows = []
start = date(2025, 11, 18)
products = [("P001", 20, 19.99), ("P002", 35, 24.99), ("P003", 15, 29.99)]

for i in range(120):
    d = start + timedelta(days=i)
    for pid, base_qty, base_price in products:
        promo = d.weekday() in (4, 5)
        price = base_price * 0.9 if promo else base_price
        qty = max(1.0, base_qty + (d.day % 7) + (i * 0.05) + np.random.normal(0, 1.5))
        rows.append({
            "date": d,
            "product_id": pid,
            "quantity": round(qty, 2),
            "price": price,
            "promo_flag": int(promo),
            "revenue": round(qty * price, 2),
        })

df = pd.DataFrame(rows)
print(f"  Radku      : {len(df)}")
print(f"  Rozsah     : {df['date'].min()} --> {df['date'].max()}")
print(f"  Produkty   : {sorted(df['product_id'].unique().tolist())}")
print(f"  Avg qty    : {df['quantity'].mean():.2f}")


# ── 2. TIME-BASED SPLIT ─────────────────────────────────────────────────────
banner("KROK 2 -- Time-based split  (train ~75d / test ~45d)")

split_date = date(2026, 2, 1)
train_df, test_df = time_based_split_by_date(df, DATE_COL, split_date)

print(f"  Split date : {split_date}")
print(f"  Train      : {len(train_df)} radku  [{train_df['date'].min()} --> {train_df['date'].max()}]")
print(f"  Test       : {len(test_df)} radku   [{test_df['date'].min()} --> {test_df['date'].max()}]")

leakage_ok = train_df["date"].max() < split_date
print(f"  Leakage    : {'ZADNY (OK)' if leakage_ok else 'POZOR: LEAKAGE!'}")
assert leakage_ok, "Data leakage detected!"


# ── 3. TRENINK ───────────────────────────────────────────────────────────────
banner("KROK 3 -- Trenink LightGBM (pouze na train datech)")

artifacts_dir = tempfile.mkdtemp(prefix="lgb_demo_")
booster, meta = train_model(
    df,
    data_from=train_df["date"].min(),
    data_to=train_df["date"].max(),
    split_date=split_date,
    artifacts_dir=artifacts_dir,
)

src = meta["eval_source"]
src_label = "out-of-sample (OK)" if src == "test" else "in-sample (pozor!)"
print(f"  eval_source: {src}  <-- {src_label}")
print(f"  MAE        : {meta['mae']:.4f}")
print(f"  RMSE       : {meta['rmse']:.4f}")
print(f"  MAPE       : {meta['mape']:.2f}%")
print(f"  n eval     : {meta['n_eval_samples']}")


# ── 4. EVALUATE TIME SPLIT ───────────────────────────────────────────────────
banner("KROK 4 -- evaluate_time_split: predikce vs skutecnost")


def predict_fn(d):
    return predict(booster, d)


ev = evaluate_time_split(train_df, test_df, predict_fn)
print(f"  MAE        : {ev['mae']:.4f}  (prumerna abs. chyba v kusech)")
print(f"  RMSE       : {ev['rmse']:.4f}  (penalizuje velke odchylky)")
print(f"  MAPE       : {ev['mape']:.2f}%  (prumerna % chyba)")
print(f"  n_samples  : {ev['n_samples']}")
dr = ev["date_range"]
print(f"  Train      : {dr['train_start']} --> {dr['train_end']}")
print(f"  Test       : {dr['test_start']} --> {dr['test_end']}")


# ── 5. DETAIL P001 ───────────────────────────────────────────────────────────
banner("KROK 5 -- Predikce vs Skutecnost: P001, prvnich 10 dni")

p001_train = train_df[train_df["product_id"] == "P001"]
p001_test = test_df[test_df["product_id"] == "P001"].sort_values("date")
feat = _compute_test_features_with_context(p001_train, p001_test)
preds_p001 = predict(booster, feat)

header = f"  {'Datum':<12} {'Skutecnost':>12} {'Predikce':>10} {'Chyba':>8} {'Chyba%':>8}"
print(header)
print("  " + "-" * 56)
for i, (_, row) in enumerate(p001_test.head(10).iterrows()):
    p = preds_p001[i]
    a = row["quantity"]
    err = p - a
    pct = (err / (a + 1e-8)) * 100
    s = "+" if err > 0 else ""
    print(f"  {str(row['date']):<12} {a:>12.2f} {p:>10.2f} {s+f'{err:.2f}':>8} {s+f'{pct:.1f}%':>8}")


# ── 6. ROLLING BACKTEST ─────────────────────────────────────────────────────
banner("KROK 6 -- Rolling backtest (okno=60d, krok=7d)")

actuals_arr, preds_arr, test_dates = rolling_backtest(
    df,
    date_col=DATE_COL,
    entity_col=ENTITY_COL,
    predict_fn=predict_fn,
    train_window_days=60,
    step_days=7,
)

rm = backtest_metrics(actuals_arr, preds_arr)
print(f"  Celkem pred: {len(preds_arr)}")
print(f"  MAE        : {rm['mae']:.4f}")
print(f"  RMSE       : {rm['rmse']:.4f}")
print(f"  MAPE       : {rm['mape']:.2f}%")
if test_dates:
    print(f"  Test rozsah: {min(test_dates)} --> {max(test_dates)}")


# ── 7. IN-SAMPLE vs OUT-OF-SAMPLE ───────────────────────────────────────────
banner("KROK 7 -- In-sample vs Out-of-sample srovnani")

_, in_meta = train_model(
    train_df,
    data_from=train_df["date"].min(),
    data_to=train_df["date"].max(),
    split_date=None,
    artifacts_dir=artifacts_dir,
)

print(f"  {'Metrika':<6} {'In-sample (train)':>20} {'Out-of-sample (test)':>22}")
print("  " + "-" * 50)
print(f"  {'MAE':<6} {in_meta['mae']:>20.4f} {ev['mae']:>22.4f}")
print(f"  {'RMSE':<6} {in_meta['rmse']:>20.4f} {ev['rmse']:>22.4f}")
print(f"  {'MAPE':<6} {in_meta['mape']:>19.2f}% {ev['mape']:>21.2f}%")

if in_meta["mae"] < ev["mae"]:
    gap = ((ev["mae"] - in_meta["mae"]) / in_meta["mae"]) * 100
    print(f"\n  Out-of-sample MAE je o {gap:.1f}% horsi nez in-sample")
    print("  (normalni – model na trenovacich datech overfituje mene)")

print()
print(SEP)
print("HOTOVO -- backtesting pipeline kompletne funkcni")
print(SEP)

shutil.rmtree(artifacts_dir, ignore_errors=True)
