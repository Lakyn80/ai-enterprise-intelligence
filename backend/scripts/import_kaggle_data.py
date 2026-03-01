#!/usr/bin/env python3
"""Import Kaggle retail_store_inventory.csv into sales_facts. Run from backend/ or via docker."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.forecasting.import_kaggle import import_csv

if __name__ == "__main__":
    n = asyncio.run(import_csv("/data/retail_store_inventory.csv"))
    print(f"Imported {n} aggregated rows into sales_facts")
