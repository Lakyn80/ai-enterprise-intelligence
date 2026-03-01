# Retail Forecast Platform

Data-driven forecasting and AI decision support for retail. Modular monorepo with FastAPI backend, Next.js frontend, LightGBM forecasting, and LangChain/LangGraph AI assistants.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis, LightGBM, LangChain, LangGraph
- **Frontend**: Next.js 14 (App Router), TypeScript, TailwindCSS
- **LLM**: modulární (OpenAI/DeepSeek), default DeepSeek

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env – DEEPSEEK_API_KEY (default), OPENAI_API_KEY (volitelně)
```

### 2. Run with Docker Compose

```bash
docker compose up -d
```

- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **PostgreSQL**: localhost:5433 (host port to avoid conflict with local Postgres)
- **Redis**: localhost:6379

### 3. Historická data (Kaggle) – vše v Dockeru

Pro reálná historická data:

1. **Kaggle token**: [Create API Token](https://www.kaggle.com/settings) → ulož `kaggle.json` do `%USERPROFILE%\.kaggle\`

2. **Stáhnout dataset v Dockeru** (PowerShell – na Windows použij tento skript):
   ```powershell
   .\scripts\download-kaggle-data.ps1
   ```
   Na Linux/Mac: `make kaggle-download`

3. **Import v Dockeru** (backend musí běžet):
   ```powershell
   .\scripts\import-kaggle.ps1
   ```
   Nebo: `make import-kaggle`

Vše běží v kontejnerech – download i API volání jdou přes `docker compose run` resp. `docker compose exec`.

Alternativa – demo data (seed):
```powershell
make seed
```

### 4. Train the model

```bash
curl -X POST "http://localhost:8000/api/admin/train?from_date=2024-01-01&to_date=2025-03-01" \
  -H "X-Api-Key: dev-admin-key-change-in-production"
```

### 5. Query forecast

```bash
curl "http://localhost:8000/api/forecast?product_id=P001&from_date=2025-03-01&to_date=2025-03-31"
```

## Running without Docker

### Backend

```bash
cd backend
pip install -e ".[dev]"
# Ensure PostgreSQL and Redis are running
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/retail_forecast
export DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5433/retail_forecast
alembic -c app/db/migrations upgrade  # or use env.py path
# Or: alembic upgrade head  (if script_location points to app/db/migrations)
uvicorn app.main:create_app --factory --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|-------|----------|-------------|
| GET | /api/health | Health check |
| GET | /api/metrics | Simple metrics |
| POST | /api/admin/seed | Seed demo data (API key) |
| POST | /api/admin/import-kaggle | Import Kaggle CSV (API key) |
| POST | /api/admin/train | Train model (API key) |
| GET | /api/forecast | Get forecast |
| POST | /api/scenario/price-change | Price change scenario |
| POST | /api/assistant/chat | AI analyst chat |
| POST | /api/knowledge/reset | Reset RAG store (API key) |
| POST | /api/knowledge/ingest | Ingest documents (API key) |
| POST | /api/knowledge/query | Query RAG |

## RAG reset + re-ingest (po změně embeddings) – v Dockeru

```powershell
.\scripts\rag-reset-and-ingest.ps1
```
Nebo: `make rag-reset` a `make rag-ingest`

## Tests

```bash
cd backend
pytest tests/ -v
```

## Configuration (.env)

- `DATABASE_URL` / `DATABASE_URL_SYNC` – PostgreSQL (port 5433 for local)
- `REDIS_URL` – Redis
- `API_KEY_ADMIN` – Admin API key
- `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` – LLM (modulární přepínač v UI)
- `RAG_ENABLED` – Enable RAG (true/false)
- `VECTORSTORE` – chroma \| faiss
- `EMBEDDINGS_PROVIDER` – local \| openai (default local)
- `NEXT_PUBLIC_API_URL` – API base for frontend

## Project Structure

```
backend/
  app/
    main.py           # FastAPI factory
    settings.py
    core/             # Logging, security, deps
    db/               # SQLAlchemy, migrations
    shared/
    connectors/       # ERP, ecommerce, CRM, marketing, scraping (interfaces + dummies)
    forecasting/      # Features, training, backtest, service, router
    ai_assistant/     # Providers, tools, graph, service, router
    knowledge_rag/     # Vector stores, ingest, service, router
  scripts/seed_demo_data.py
  tests/
frontend/
  app/                # Next.js App Router pages
  components/
  lib/
docker-compose.yml
```
