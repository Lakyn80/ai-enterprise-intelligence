# Download Kaggle dataset v Dockeru – vše běží v backend kontejneru
# Kaggle token: https://www.kaggle.com/settings -> Create API Token -> ulož do $env:USERPROFILE\.kaggle\kaggle.json

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$dataDir = Join-Path $root "data"
$kaggleDir = Join-Path $env:USERPROFILE ".kaggle"
$dataset = "anirudhchauhan/retail-store-inventory-forecasting-dataset"

if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
    Write-Host "Created $dataDir"
}

if (-not (Test-Path (Join-Path $kaggleDir "kaggle.json"))) {
    Write-Host "Kaggle token not found. Create at https://www.kaggle.com/settings" -ForegroundColor Yellow
    Write-Host "Save kaggle.json to $kaggleDir" -ForegroundColor Yellow
    exit 1
}

Push-Location $root
try {
    Write-Host "Downloading Kaggle dataset in Docker..." -ForegroundColor Cyan
    $kaggleMount = "${kaggleDir}:/root/.kaggle:ro"
    docker compose run --rm `
        -v "${root}/data:/data" `
        -v "${kaggleMount}" `
        -w /data backend sh -c "kaggle datasets download -d $dataset && (unzip -o retail-store-inventory-forecasting-dataset.zip 2>/dev/null || python -m zipfile -e retail-store-inventory-forecasting-dataset.zip .) && ls -la"
} finally {
    Pop-Location
}

Write-Host "`nNext: Import via Docker:" -ForegroundColor Cyan
Write-Host "  .\scripts\import-kaggle.ps1" -ForegroundColor White
