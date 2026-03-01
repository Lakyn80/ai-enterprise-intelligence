# Import Kaggle data v Dockeru – curl uvnitř backend kontejneru (run download-kaggle-data.ps1 first)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$apiKey = $env:API_KEY_ADMIN
if (-not $apiKey) { $apiKey = "dev-admin-key-change-in-production" }
Push-Location $root
docker compose exec backend curl -s -X POST "http://localhost:8000/api/admin/import-kaggle" -H "X-Api-Key: $apiKey"
Pop-Location
