# AI Enterprise Intelligence — Developer README

> Retail Forecast Platform: FastAPI + LightGBM + ChromaDB + Next.js

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Tech Stack](#3-tech-stack)
4. [Environment Variables](#4-environment-variables)
5. [Running Locally (Docker)](#5-running-locally-docker)
6. [Running Locally (without Docker)](#6-running-locally-without-docker)
7. [API Endpoints Reference](#7-api-endpoints-reference)
8. [Forecasting Module](#8-forecasting-module)
9. [Knowledge Assistant & RAG](#9-knowledge-assistant--rag)
10. [Knowledge Reports — DB → ChromaDB Pipeline](#10-knowledge-reports--db--chromadb-pipeline)
11. [AI Assistant (Chat)](#11-ai-assistant-chat)
12. [Pricing Optimization](#12-pricing-optimization)
13. [Frontend Pages](#13-frontend-pages)
14. [Adding a New Report Type](#14-adding-a-new-report-type)
15. [Adding a New Embedding Provider](#15-adding-a-new-embedding-provider)
16. [Troubleshooting](#16-troubleshooting)
17. [Changelog](#17-changelog)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Next.js Frontend                    │
│        (port 3030)  — Forecast, Admin, Knowledge UI      │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend                        │
│                      (port 8000)                         │
│                                                          │
│  ┌─────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │ Forecasting │  │ AI Assistant  │  │  Knowledge    │  │
│  │  (LightGBM) │  │  (DeepSeek)   │  │  RAG (Chroma) │  │
│  └──────┬──────┘  └───────┬───────┘  └───────┬───────┘  │
│         │                 │                  │           │
│  ┌──────▼─────────────────▼──────────────────▼───────┐   │
│  │       PostgreSQL  (sales_facts, model_artifacts)   │   │
│  └────────────────────────────────────────────────── ┘   │
│  ┌─────────────────────────────────────────────────── ┐   │
│  │            ChromaDB (vector store, persisted)       │   │
│  └─────────────────────────────────────────────────── ┘   │
└─────────────────────────────────────────────────────────┘
```

**Data flow — Forecasting:**
```
Kaggle CSV → PostgreSQL (sales_facts) → LightGBM model → Forecast API → Frontend
```

**Data flow — Knowledge Assistant:**
```
PostgreSQL → aggregation → text reports → chunking → ChromaDB → similarity search → DeepSeek LLM → answer
```

---

## 2. Repository Structure

```
ai-enterprise-intelligence/
├── backend/
│   └── app/
│       ├── main.py                    # FastAPI app factory
│       ├── settings.py                # All config via env vars (Pydantic)
│       ├── core/
│       │   ├── security.py            # API key verification
│       │   ├── deps.py                # FastAPI dependency injection
│       │   └── logging.py             # Structured logging setup
│       ├── db/
│       │   ├── base.py                # SQLAlchemy declarative base
│       │   ├── session.py             # Async + sync engine, session deps
│       │   └── migrations/            # Alembic migrations
│       ├── forecasting/
│       │   ├── router.py              # All forecasting endpoints
│       │   ├── service.py             # Train, forecast, backtest orchestration
│       │   ├── repository.py          # DB access layer (sales_facts)
│       │   ├── db_models.py           # SalesFact, ModelArtifact ORM models
│       │   ├── features.py            # Feature engineering (lags, rolling, etc.)
│       │   ├── training.py            # LightGBM train/predict
│       │   ├── backtest.py            # Rolling backtest, time-split evaluation
│       │   ├── import_kaggle.py       # CSV → PostgreSQL import
│       │   ├── schemas.py             # Pydantic schemas for forecasting API
│       │   ├── pricing_engine.py      # Pricing optimization (scipy)
│       │   ├── pricing_service.py     # Pricing orchestration
│       │   ├── pricing_router.py      # Pricing API endpoints
│       │   ├── pricing_schemas.py     # Pydantic schemas for pricing
│       │   └── pricing_constraints.py # Constraint validation
│       ├── knowledge_rag/
│       │   ├── router.py              # RAG endpoints (/knowledge/*)
│       │   ├── service.py             # KnowledgeService: ingest + query
│       │   ├── schemas.py             # Pydantic schemas for RAG API
│       │   ├── ingest/
│       │   │   ├── chunking.py        # Sentence-aware word-based chunking
│       │   │   ├── embeddings.py      # EmbeddingProvider (DeepSeek/OpenAI/Stub)
│       │   │   └── loaders.py         # File/folder document loaders
│       │   └── vectorstores/
│       │       ├── base.py            # VectorStore abstract interface
│       │       ├── chroma_store.py    # ChromaDB adapter (default)
│       │       └── faiss_store.py     # FAISS adapter (optional)
│       ├── knowledge_reports/
│       │   ├── generator.py           # ReportGenerator Protocol + implementations
│       │   └── service.py             # KnowledgeReportService orchestrator
│       └── ai_assistant/
│           ├── router.py              # /assistant/chat, /assistant/explain-forecast
│           ├── service.py             # Chat orchestration with tool use
│           ├── schemas.py             # ChatRequest, ChatResponse
│           ├── providers/
│           │   ├── base.py            # LLMProvider abstract interface
│           │   ├── deepseek_provider.py
│           │   └── openai_provider.py
│           ├── tools/
│           │   ├── data_tools.py      # Tool: fetch sales data
│           │   ├── forecast_tools.py  # Tool: run forecast
│           │   └── knowledge_tools.py # Tool: query RAG
│           └── graph/
│               └── agent_graph.py     # LangGraph agent execution
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                 # Root layout, sidebar nav
│   │   ├── page.tsx                   # Dashboard home
│   │   ├── forecast/page.tsx          # Forecast + backtest UI
│   │   ├── admin/page.tsx             # Admin: seed, train model
│   │   ├── knowledge/page.tsx         # Knowledge Assistant chat UI
│   │   └── pricing/page.tsx           # Pricing optimization UI
│   ├── components/
│   │   ├── ForecastChart.tsx          # Recharts forecast vs actuals chart
│   │   └── ScenarioForm.tsx           # Price scenario comparison form
│   └── lib/
│       ├── api.ts                     # All API calls (fetch wrappers)
│       └── types.ts                   # TypeScript types
├── scripts/
│   ├── download-kaggle-data.ps1       # Download Kaggle dataset (Windows/Docker)
│   ├── import-kaggle.ps1              # Trigger import via API (Windows)
│   └── download_kaggle_data.sh        # Download Kaggle dataset (Linux/Mac)
├── docker-compose.yml                 # Full stack: postgres, redis, backend, frontend
└── .env                               # Local secrets (not committed)
```

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.110+ |
| ML model | LightGBM (gradient boosted trees) |
| Vector store | ChromaDB (default) / FAISS (optional) |
| LLM | DeepSeek (default) / OpenAI (optional) |
| Embeddings | DeepSeek `deepseek-embedding` / OpenAI `text-embedding-3-small` / Stub |
| Agent framework | LangGraph |
| Database | PostgreSQL 16 |
| Cache / queue | Redis 7 |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts |
| Container | Docker + Docker Compose |

---

## 4. Environment Variables

Create a `.env` file in the project root:

```env
# === Database ===
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/retail_forecast
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5433/retail_forecast

# === Redis ===
REDIS_URL=redis://localhost:6380/0
REDIS_HOST_PORT=6380        # Docker host port for Redis; container still listens on 6379
ASSISTANTS_CACHE_TTL=0        # 0 = preset Q&A stay in Redis until you delete them

# === Security ===
API_KEY_ADMIN=dev-admin-key-change-in-production

# === LLM Providers ===
DEEPSEEK_API_KEY=sk-...         # Required for LLM answers and embeddings
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-...           # Optional, only if EMBEDDINGS_PROVIDER=openai

# === RAG / Vector store ===
RAG_ENABLED=true
VECTORSTORE=chroma              # chroma | faiss
EMBEDDINGS_PROVIDER=deepseek    # deepseek | openai | local (stub)
RAG_COLLECTION_NAME=retail_knowledge
RAG_CHROMA_PATH=./chroma_db     # Host path; Docker uses /app/chroma_db

# === Application ===
LOG_LEVEL=INFO
DEBUG=false
ARTIFACTS_PATH=./artifacts      # Docker uses /app/artifacts

# === Frontend ===
NEXT_PUBLIC_API_URL=http://localhost:8001
```

> **Docker note:** `DATABASE_URL` and `REDIS_URL` are overridden in `docker-compose.yml`
> to use container hostnames (`postgres`, `redis`). The `.env` values are used for local dev.
> Inside Docker Compose the backend still connects to `redis://redis:6379/0`; `6380` is only the host-side local dev port.
> In `docker-compose.prod.yml`, Redis is published as host port `6380` by default (`REDIS_HOST_PORT`), because `6379` may already be occupied on the server.

---

## 5. Running Locally (Docker)

**Prerequisites:** Docker Desktop, Kaggle account (optional for real data)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — add DEEPSEEK_API_KEY at minimum

# 2. Start all services
docker compose up -d --build

# 3. Check services are healthy
docker compose ps

# 4. (Optional) Load Kaggle data
.\scripts\download-kaggle-data.ps1   # Windows
# or: ./scripts/download_kaggle_data.sh  # Linux/Mac (requires kaggle CLI)

# 5. Import data into PostgreSQL
curl -X POST http://localhost:8001/api/admin/import-kaggle \
  -H "X-Api-Key: dev-admin-key-change-in-production"

# 6. Train the forecasting model
curl -X POST http://localhost:8001/api/admin/train \
  -H "X-Api-Key: dev-admin-key-change-in-production"

# 7. Ingest reports into Knowledge Assistant
curl -X POST http://localhost:8001/api/knowledge/ingest-reports \
  -H "X-Api-Key: dev-admin-key-change-in-production"

# 8. Warm all 40 preset Q&A into Redis and translate demo locales
docker compose run --rm cache-warmup
```

| Service | URL |
|---|---|
| Frontend | http://localhost:4000 |
| Backend API | http://localhost:8001 |
| API Docs (Swagger) | http://localhost:8001/docs |
| PostgreSQL | internal container only |
| Redis | internal container only |

Preset cache notes:
- `docker compose run --rm cache-warmup` fills all 20 `knowledge` + 20 `analyst` preset answers in English and translates them to `cs/sk/ru`.
- Preset answers are stored in Redis without expiry by default (`ASSISTANTS_CACHE_TTL=0`).
- Redis survives restart because both local and production compose files now persist `/data` in the `redis_data` Docker volume.
- Data is deleted only by `docker compose down -v` or explicit cache flush.

---

## 6. Running Locally (without Docker)

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# Start PostgreSQL and Redis separately, then:
uvicorn app.main:create_app --factory --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev     # http://localhost:3000
```

---

## 7. API Endpoints Reference

### Health & Metrics
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/health` | — | Liveness check |
| GET | `/api/metrics` | — | Request counters |

### Admin
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/admin/seed` | API key | Seed 360 demo rows (P001–P003) |
| POST | `/api/admin/import-kaggle` | API key | Import Kaggle CSV from `/data/` |
| POST | `/api/admin/train` | API key | Train LightGBM model |

**Train parameters** (query params, all optional):
- `from_date` / `to_date` — auto-detected from DB if omitted (max 3 years)
- `split_date` — enables out-of-sample evaluation (train on `[from, split)`, eval on `[split, to]`)

### Forecasting
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/forecast` | — | Get forecast for product + date range |
| GET | `/api/backtest` | — | Rolling backtest (MAE, RMSE, MAPE) |
| GET | `/api/data/products` | — | List product IDs |
| GET | `/api/data/historical` | — | Aggregated historical sales |
| POST | `/api/scenario/price-change` | — | Forecast with price delta |

### Pricing Optimization
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/pricing/optimize` | — | Run pricing optimization |

### Knowledge / RAG
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/knowledge/ingest` | API key | Ingest text or folder of documents |
| POST | `/api/knowledge/ingest-reports` | API key | Generate DB reports → ingest to ChromaDB |
| POST | `/api/knowledge/query` | — | Query RAG, returns LLM answer + citations |
| POST | `/api/knowledge/reset` | API key | Reset ChromaDB collection |

### AI Assistant
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/assistant/chat` | — | Chat with AI analyst (tool use) |
| POST | `/api/assistant/explain-forecast` | — | Explain forecast for product |

---

## 8. Forecasting Module

### How it works

1. **Data ingestion** — Kaggle CSV parsed by `import_kaggle.py`, aggregated by `(date, product_id)`, stored in `sales_facts` table
2. **Feature engineering** (`features.py`) — lag features (7, 14, 30 days), rolling means (7, 14, 30 days), day-of-week, month, promo flag, price features
3. **Training** (`training.py`) — LightGBM regressor, serialized to `artifacts/model_<version>.pkl`
4. **Forecast** — loads model artifact, engineers features for future dates, returns predicted quantity + revenue
5. **Backtest** (`backtest.py`) — rolling window evaluation with strict no-leakage guarantee

### Backtest

Uses a **rolling window** approach:
- Training window: 90 days (default)
- Step: 7 days
- Test features are computed with **training context** (last 30 rows per product prepended) to ensure lag features are valid
- `train_end < test_start` is **asserted** on every window — zero leakage

Backtest on the **Forecast page** automatically uses a 6-month window to get enough samples (`n ≈ 150+`) for representative MAPE.

### Auto-detected training range

When `from_date` / `to_date` are left empty in Admin:
```
to_date   = max(sales_facts.date)
from_date = max(min_db_date, to_date - 3 years)
```

---

## 9. Knowledge Assistant & RAG

### Pipeline overview

```
Text / Reports
      ↓
chunk_text()          ← sentence-aware, word-based (200 words, 30 overlap)
      ↓
context_prefix + chunk  ← "Product P0001 sales report (2022-01-01 to 2024-12-31): ..."
      ↓
embed_documents()     ← DeepSeek / OpenAI / Stub
      ↓
ChromaDB.add()        ← with structured metadata per chunk
      ↓
similarity_search()   ← cosine distance, k=4
      ↓
DeepSeek LLM          ← generates answer from retrieved context
      ↓
answer + citations
```

### Chunking strategy (`knowledge_rag/ingest/chunking.py`)

- **Sentence-aware**: splits on `.`, `!`, `?` — chunks never cut mid-sentence
- **Word-based**: `chunk_size=200 words`, `overlap=30 words`
- **Edge case safe**: single sentence longer than `chunk_size` is emitted as-is

### Structured metadata in ChromaDB

Every chunk stores:
```json
{
  "source": "report:product:P0001",
  "report_type": "product",
  "product_id": "P0001",
  "date_from": "2022-01-01",
  "date_to": "2024-12-31",
  "chunk_index": 0,
  "total_chunks": 3
}
```
This enables future filtered retrieval: `where={"product_id": "P0001"}`.

### Embedding providers (`knowledge_rag/ingest/embeddings.py`)

| Provider | Model | Set via |
|---|---|---|
| `deepseek` (default) | `deepseek-embedding` | `DEEPSEEK_API_KEY` |
| `openai` | `text-embedding-3-small` | `OPENAI_API_KEY` + `EMBEDDINGS_PROVIDER=openai` |
| `local` (stub) | SHA-256 hash | automatic fallback when no API key |

> The stub provides random-ish 1024-dim vectors — retrieval quality is low, use only for local dev without API keys.

---

## 10. Knowledge Reports — DB → ChromaDB Pipeline

### Why not raw CSV?

Raw CSV rows (numeric tabular data) embed poorly — semantic similarity search cannot match
`"2023-01-01, P001, 45.0"` to a question like *"What are the sales trends?"*.
Text reports derived from aggregated statistics work far better.

### Report types

**ProductReportGenerator** — one document per product:
```
Product P0001
Date range: 2022-01-01 to 2024-12-31 (730 days of data)
Category: Electronics

Sales summary:
- Total sales: 475,000 units
- Average daily sales: 650.7 units/day
- Peak sales: 1,200 units (on 2023-12-24)
- Minimum sales day: 120 units
- Sales volatility: moderate (std dev: 130.5)

Trends:
- 30-day trend: increasing
- Average price: 49.50
- Promo lift: +18.3% (810.2 vs 685.1 units/day)
```

**CategoryReportGenerator** — one document per category:
```
Category Electronics
Date range: 2022-01-01 to 2024-12-31
Products in category: 12
Total category sales: 5,700,000 units
Average daily sales (all products): 7,808.2 units/day
30-day trend: stable
Top products by volume: P0001, P0023, P0047
```

### Usage

```bash
# First time (or after new data import):
curl -X POST http://localhost:8000/api/knowledge/ingest-reports \
  -H "X-Api-Key: dev-admin-key-change-in-production"

# Response:
{
  "status": "ok",
  "date_from": "2022-01-01",
  "date_to": "2024-12-31",
  "products": {"count": 50, "chunks": 147},
  "categories": {"count": 8, "chunks": 24},
  "ingested": 171
}
```

After ingestion, Knowledge Assistant can answer:
- *"Which product has the highest sales?"*
- *"What is the trend for Electronics category?"*
- *"Which products have high volatility?"*
- *"What was the best promo lift?"*

---

## 11. AI Assistant (Chat)

The assistant uses a **LangGraph agent** with tool use:

| Tool | Description |
|---|---|
| `get_sales_data` | Fetch historical sales from DB |
| `get_forecast` | Run forecast for product + date range |
| `query_knowledge` | Search ChromaDB RAG knowledge base |

**Providers:** DeepSeek (default, `deepseek-chat`) or OpenAI (`gpt-4o`).

```bash
curl -X POST http://localhost:8000/api/assistant/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the sales trends for the top products?", "provider": "deepseek"}'
```

---

## 12. Pricing Optimization

Located in `forecasting/pricing_*.py`. Uses `scipy.optimize` to find optimal price points given:
- Demand elasticity (estimated from sales data)
- Revenue constraints
- Min/max price bounds

```bash
curl -X POST http://localhost:8000/api/pricing/optimize \
  -H "Content-Type: application/json" \
  -d '{"product_id": "P0001", "from_date": "2024-01-01", "to_date": "2024-03-31"}'
```

---

## 13. Frontend Pages

| Page | Path | Description |
|---|---|---|
| Dashboard | `/` | Overview and quick stats |
| Forecast | `/forecast` | Product forecast chart, actuals overlay, backtest metrics, price scenario |
| Admin | `/admin` | Seed data, train model, configure date ranges |
| Knowledge | `/knowledge` | Chat with Knowledge Assistant |
| Pricing | `/pricing` | Pricing optimization UI |

**Frontend is built at Docker image build time.** `NEXT_PUBLIC_API_URL` is baked in.
After changing it: `docker compose up -d --build frontend`

---

## 14. Adding a New Report Type

1. Add a new generator class in [backend/app/knowledge_reports/generator.py](backend/app/knowledge_reports/generator.py):

```python
class WeeklyTrendReportGenerator:
    def generate(
        self, group_id: str, df: pd.DataFrame, date_from: date, date_to: date
    ) -> tuple[str, dict]:
        # compute stats, build text
        text = f"Weekly trend for {group_id}:\n..."
        meta = {
            "report_type": "weekly_trend",
            "source": f"report:weekly:{group_id}",
            "date_from": str(date_from),
            "date_to": str(date_to),
        }
        return text, meta
```

2. Register in [backend/app/knowledge_reports/service.py](backend/app/knowledge_reports/service.py) inside `ingest_reports()`:

```python
w_ingested, w_warnings = await _ingest_reports_for_groups(
    weekly_groups, date_from, date_to,
    WeeklyTrendReportGenerator(), self._knowledge,
)
results["weekly_trends"] = {"count": len(weekly_groups), "chunks": w_ingested}
```

No other files need to change.

---

## 15. Adding a New Embedding Provider

1. Add a class in [backend/app/knowledge_rag/ingest/embeddings.py](backend/app/knowledge_rag/ingest/embeddings.py) implementing `EmbeddingProvider`
2. Register in `get_embedding_provider()`:

```python
if settings.embeddings_provider == "mymodel":
    return MyModelEmbeddingProvider()
```

3. Set `EMBEDDINGS_PROVIDER=mymodel` in `.env`

> **Important:** After switching embedding provider, reset ChromaDB and re-ingest:
> ```bash
> curl -X POST http://localhost:8000/api/knowledge/reset -H "X-Api-Key: ..."
> curl -X POST http://localhost:8000/api/knowledge/ingest-reports -H "X-Api-Key: ..."
> ```
> Mixing embeddings from different models in the same collection breaks retrieval.

---

## 16. Troubleshooting

### `[Errno -2] Name or service not known` (postgres/redis DNS)
Backend cannot resolve container hostnames. Usually means a container is not on `app_net`.
```bash
docker network inspect ai-enterprise-intelligence_app_net
docker compose down && docker compose up -d
```

### Port 8000 already allocated
```bash
docker ps -a | grep 8000
docker rm -f <container_id>
docker compose up -d
```

### Backtest returns `n=0` or `Insufficient data`
Need at least `train_window_days + step_days` rows per product. The Forecast page automatically uses a 6-month backtest window to ensure enough samples.

### Knowledge Assistant returns raw excerpts instead of LLM answer
`DEEPSEEK_API_KEY` is missing or invalid — service falls back to raw text. Check:
```bash
docker compose exec backend env | grep DEEPSEEK
```

### ChromaDB empty after container restart
ChromaDB is persisted to Docker volume `chroma_data`. Data survives restarts. It is only lost after `docker compose down -v`.

### Frontend shows old data after backend change
Next.js is compiled into the Docker image. Rebuild frontend:
```bash
docker compose up -d --build frontend
```

---

## 17. Changelog

### 2026-03-19 (patch)

**Bug fix — infinite loop in `chunk_text`** (`knowledge_rag/ingest/chunking.py`)
- Short texts (< `chunk_size` words) caused `i` to never advance → infinite loop → ingest hung indefinitely
- Fix: after sliding overlap window, always guarantee `i` advances by at least 1 sentence; break when all sentences consumed

### 2026-03-19

**Knowledge Reports pipeline (new module `knowledge_reports/`)**
- `ReportGenerator` Protocol — contract for all report types
- `ProductReportGenerator` — aggregates per-product stats (avg, total, peak, trend, volatility, promo lift) into human-readable text
- `CategoryReportGenerator` — aggregates per-category stats (total, n_products, trend, top products)
- `KnowledgeReportService` — orchestrates DB → reports → ChromaDB; pluggable (add new generators in 4 lines)
- New endpoint `POST /api/knowledge/ingest-reports` (API key required)

**Chunking improvement (`knowledge_rag/ingest/chunking.py`)**
- Changed from **character-based** to **sentence-aware word-based** chunking
- `chunk_size=200 words`, `overlap=30 words` — never cuts mid-sentence
- Edge cases handled: single oversized sentence, empty text

**Structured metadata in ChromaDB**
- Every chunk now stores `product_id`, `report_type`, `date_from/to`, `chunk_index`, `total_chunks`
- Enables future filtered retrieval via `where={"product_id": "..."}`

**Context prefix on chunks**
- Each chunk is prepended with `"Product P0001 sales report (2022-01-01 to 2024-12-31): "` before embedding
- Improves semantic retrieval — embedding model sees the subject of each chunk

**`KnowledgeService.ingest_text()` extended**
- Added `metadata: dict | None` parameter — structured metadata passed to ChromaDB
- Added `context_prefix: str` parameter — prepended to chunk text before embedding
- Fully backward compatible — existing callers work without changes

### Earlier

- Docker networking: explicit `app_net` bridge network — fixed `[Errno -2] Name or service not known`
- Auto-detected training date range: max 3 years from latest DB record
- Backtest time-split leakage fix: `test_start = train_end + 1 day` (was using next available date)
- Forecast page backtest extended to 6-month window for representative `n` samples
- DeepSeek LLM integrated into RAG `query()` — answers generated from retrieved context
- Pricing optimization module added (`pricing_engine.py`, `pricing_service.py`, `pricing_router.py`)
