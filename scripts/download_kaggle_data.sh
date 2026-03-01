#!/bin/sh
# Download and extract Kaggle retail forecasting dataset
set -e
mkdir -p data
cd data
echo "Downloading dataset..."
kaggle datasets download -d anirudhchauhan/retail-store-inventory-forecasting-dataset
echo "Extracting..."
if [ -f retail-store-inventory-forecasting-dataset.zip ]; then
  unzip -o retail-store-inventory-forecasting-dataset.zip || python -m zipfile -e retail-store-inventory-forecasting-dataset.zip .
else
  tar -xf retail-store-inventory-forecasting-dataset.zip 2>/dev/null || true
fi
echo "Done. Files in data/:"
ls -la
