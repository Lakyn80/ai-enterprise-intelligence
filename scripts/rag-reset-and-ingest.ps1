# RAG reset + re-ingest v Dockeru (docker compose exec backend curl)
# Spusť: docker compose up -d; pak .\scripts\rag-reset-and-ingest.ps1

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$apiKey = $env:API_KEY_ADMIN
if (-not $apiKey) { $apiKey = "dev-admin-key-change-in-production" }

Push-Location $root

Write-Host "1. Reset RAG store..."
docker compose exec backend curl -s -X POST "http://localhost:8000/api/knowledge/reset" -H "X-Api-Key: $apiKey"
Write-Host ""

Write-Host "2. Ingest z /data/knowledge..."
docker compose exec backend curl -s -X POST "http://localhost:8000/api/knowledge/ingest" `
    -H "X-Api-Key: $apiKey" -H "Content-Type: application/json" `
    -d '{"folder_path": "/data/knowledge"}'
Write-Host ""

Pop-Location
Write-Host "Hotovo."
