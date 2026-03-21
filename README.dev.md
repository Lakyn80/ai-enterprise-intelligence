# AI Enterprise Intelligence — `README.dev`

Developer and operations reference for the current repository state.

This document is meant to be the source of truth for:
- local development
- architecture decisions
- Docker runtime
- GitHub Actions deploy/bootstrap flow
- Redis/Qdrant/RAG behavior
- deterministic facts engine
- assistant tracing and debugging

It intentionally goes deeper than [README.md](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/README.md).

## 1. Current Stack

### Core runtime
- Backend: FastAPI
- Frontend: Next.js App Router
- Database: PostgreSQL
- Cache: Redis
- Forecasting model: LightGBM
- LLM provider: DeepSeek by default
- Embeddings: DeepSeek, OpenAI, or local stub fallback

### Vector/search runtime
- Default config fallback in code: `chroma`
- Active Docker runtime now: `qdrant`
- Optional alternative still present: `faiss`

### Assistant architecture
- `Forecast`: deterministic ML predictions from model artifacts
- `🧠 Znalosti`: RAG over generated knowledge reports
- `🤖 Analytik`: tool-using assistant flow
- Preset Q&A cache: Redis
- Custom semantic cache: pluggable backend, now `Chroma` or `Qdrant`
- Exact business fact questions: deterministic facts engine, not RAG

## 2. Architecture Overview

```text
Frontend (Next.js)
  -> Backend API (FastAPI)
     -> PostgreSQL
     -> Redis
     -> Qdrant or Chroma vector backend
     -> LightGBM model artifacts
     -> DeepSeek/OpenAI APIs
```

### Separation of responsibilities

#### Forecasting
- Reads historical sales from PostgreSQL
- Trains and stores model artifacts
- Produces deterministic forecast output

#### Knowledge RAG
- Generates textual reports from structured DB data
- Splits them into chunks
- Embeds chunks
- Stores vectors in selected vector backend
- Retrieves relevant chunks
- Uses LLM only to compose answer from retrieved context

#### Deterministic facts engine
- Handles exact ranking/max/min numeric business questions
- Maps NL question to canonical spec
- Computes answer from DB aggregation
- Renders stable template answer
- Caches by canonical spec hash + data fingerprint

#### Assistant tracing
- Every assistant request gets `trace_id`
- Exact steps are stored in PostgreSQL
- Frontend can inspect trace detail

## 3. Repository Map

### Root
- [docker-compose.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/docker-compose.yml): local stack
- [docker-compose.prod.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/docker-compose.prod.yml): production stack
- [README.md](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/README.md): older/general overview
- [README.dev.md](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/README.dev.md): this file

### Backend app
- [main.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/main.py): app factory and router wiring
- [settings.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/settings.py): runtime config

### Forecasting
- [repository.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/forecasting/repository.py): DB access and deterministic aggregations
- [service.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/forecasting/service.py): train/forecast orchestration
- [db_models.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/forecasting/db_models.py): `sales_facts`, `model_artifacts`

### Assistants
- [router.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/router.py): `/api/assistants/*`
- [service.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/service.py): preset/custom orchestration
- [cache.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/cache.py): preset Redis cache
- [query_cache.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/query_cache.py): exact Redis cache + pluggable semantic backend
- [trace_recorder.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/trace_recorder.py): in-memory trace builder
- [trace_repository.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/trace_repository.py): DB persistence for trace

### Deterministic facts engine
- [service.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/facts/service.py)
- [mapper.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/facts/mapper.py)
- [schemas.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/facts/schemas.py)
- [resolver.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/facts/resolver.py)
- [renderer.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/facts/renderer.py)
- [cache.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/facts/cache.py)

### Assistant semantic cache backends
- [base.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/semantic_backends/base.py)
- [chroma_backend.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/semantic_backends/chroma_backend.py)
- [qdrant_backend.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/assistants/semantic_backends/qdrant_backend.py)

### Knowledge RAG
- [service.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_rag/service.py): vector store factory + query flow
- [router.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_rag/router.py): ingest/reset/query API
- [base.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_rag/vectorstores/base.py): vector store interface
- [chroma_store.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_rag/vectorstores/chroma_store.py)
- [qdrant_store.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_rag/vectorstores/qdrant_store.py)
- [faiss_store.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_rag/vectorstores/faiss_store.py)

### Shared vector helpers
- [qdrant_support.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/vector/qdrant_support.py)

### Knowledge reports
- [service.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_reports/service.py)
- [generator.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/app/knowledge_reports/generator.py)

### Scripts
- [warm_preset_cache.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/scripts/warm_preset_cache.py)
- [translate_preset_qa.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/scripts/translate_preset_qa.py)
- [rag_reset_and_ingest.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/scripts/rag_reset_and_ingest.py)
- [rag_reset_and_ingest_direct.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/scripts/rag_reset_and_ingest_direct.py)
- [migrate_chroma_to_qdrant.py](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/backend/scripts/migrate_chroma_to_qdrant.py)

### CI/CD
- [images.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/.github/workflows/images.yml)
- [deploy.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/.github/workflows/deploy.yml)
- [bootstrap.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/.github/workflows/bootstrap.yml)

## 4. Current Request Flow

### 4.1 Preset assistant question

```text
web preset click
-> /api/assistants/ask-preset
-> Redis preset cache lookup
-> cache hit => return cached answer
-> cache miss => generate via knowledge/analyst flow
-> store in Redis
-> return answer + trace_id
```

### 4.2 Custom assistant question

```text
web custom question
-> /api/assistants/ask-custom
-> deterministic facts route attempt
   -> if exact business fact supported:
      canonical spec
      spec hash + data fingerprint
      facts cache / DB resolver
      stable renderer
      return deterministic answer
-> else:
   exact Redis cache
   semantic cache backend (Chroma/Qdrant)
   semantic policy
   normal assistant generation
   cache write
```

### 4.3 Knowledge RAG question

```text
question
-> infer retrieval params
-> vector similarity search
-> retrieve docs
-> optional product presort
-> LLM composes final answer from context
```

## 5. Deterministic Facts Engine

### Supported in v1
- top product by quantity
- top product by revenue
- top product by average selling price
- bottom product by quantity
- bottom product by revenue
- top product by promo lift

### Why it exists
- RAG should not decide exact rankings
- vector search should not be source of truth for numeric winners
- LLM should not invent top/bottom business facts

### Canonical spec shape

```json
{
  "spec_version": 1,
  "query_type": "fact",
  "entity": "product",
  "operation": "rank",
  "metric": "quantity",
  "direction": "desc",
  "filters": {},
  "date_range": null,
  "limit": 1
}
```

### Resolution rules
- query mapper normalizes paraphrases to same spec
- resolver computes winner from `sales_facts`
- ties are explicit
- final wording is rendered by templates, not free generation
- cache key is `spec_hash + data_fingerprint`

### Example

Input:
- `Který produkt se prodává nejvíc?`

Mapped spec:
- `metric=quantity`
- `direction=desc`

Rendered answer:
- `Nejprodávanější produkt podle počtu kusů je P0001 (25 ks).`

## 6. Assistant Trace System

Every request creates a trace row and step rows in PostgreSQL.

### Trace tables
- `assistant_traces`
- `assistant_trace_steps`

### What is recorded
- raw query
- normalized query
- selected route
- cache decisions
- semantic similarity
- canonical facts spec
- resolver input/output
- retrieved docs for RAG
- LLM request/response metadata
- rendered answer
- error state and latency

### Main endpoints
- `GET /api/assistants/traces/{trace_id}`
- `GET /api/assistants/traces`

### Frontend behavior
- assistant responses return `trace_id`
- trace detail can be inspected from UI debug panel

## 7. Vector Backend Strategy

### Current reality
- code fallback default: `Chroma`
- Docker local/prod runtime: `Qdrant`
- fallback option still supported: `FAISS`

### Why Qdrant was added
- cleaner production deployment
- payload filters
- persistence and operational tooling
- better path for scaling than local embedded Chroma persistence

### Why Chroma is still kept
- safe rollback
- local fallback
- migration path without breaking current code

### Why FAISS is still present
- simple local fallback for similarity search
- not preferred for primary production backend in this repo

## 8. Environment Variables

Create a root `.env`. Main variables:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/retail_forecast
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5433/retail_forecast

# Redis
REDIS_URL=redis://localhost:6380/0
REDIS_HOST_PORT=6380
ASSISTANTS_CACHE_TTL=0

# Security
API_KEY_ADMIN=dev-admin-key-change-in-production

# LLM
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=
LLM_TEMPERATURE=0

# RAG / vector store
RAG_ENABLED=true
VECTORSTORE=qdrant
RAG_COLLECTION_NAME=retail_knowledge
RAG_CHROMA_PATH=./chroma_db
EMBEDDINGS_PROVIDER=deepseek

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_TIMEOUT=10
QDRANT_PREFER_GRPC=false
QDRANT_PATH=

# Assistant semantic cache
ASSISTANTS_SEMANTIC_CACHE_ENABLED=true
ASSISTANTS_SEMANTIC_CACHE_BACKEND=qdrant
ASSISTANTS_SEMANTIC_CACHE_COLLECTION_NAME=assistants_query_cache
ASSISTANTS_SEMANTIC_CACHE_REUSE_SIMILARITY=0.90
ASSISTANTS_SEMANTIC_CACHE_REWRITE_SIMILARITY=0.30
ASSISTANTS_SEMANTIC_CACHE_REWRITE_ENABLED=false
ASSISTANTS_SEMANTIC_CACHE_TOP_K=3
ASSISTANTS_DETERMINISTIC_FACTS_ENABLED=true

# App
LOG_LEVEL=INFO
DEBUG=false
ARTIFACTS_PATH=./artifacts

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### Important notes
- Docker compose overrides several variables for container hostnames.
- `REDIS_HOST_PORT` is host-side only.
- backend container still talks to Redis on `redis:6379`
- Qdrant container is addressed as `http://qdrant:6333` inside Docker

## 9. Local Development with Docker

### Start stack

```bash
docker compose up -d --build
docker compose ps
```

### If port 6333 is already occupied

Use a different host port for Qdrant and keep that same env var for every Compose command in the shell session.

PowerShell:

```powershell
$env:QDRANT_HOST_PORT='6337'
docker compose up -d --build
docker compose ps
curl http://localhost:8001/api/health
curl http://localhost:6337/readyz
```

Why this matters:
- the container still listens on `6333`
- only the host-side port changes
- `docker compose --profile tools run --rm cache-warmup` must use the same `QDRANT_HOST_PORT`

### URLs
- Frontend: `http://localhost:4000`
- Backend: `http://localhost:8001`
- Swagger: `http://localhost:8001/docs`
- Qdrant: `http://localhost:6333/dashboard`

### Local containers
- `postgres`
- `redis`
- `qdrant`
- `backend`
- `frontend`
- `cache-warmup` profile service

### Volumes
- `postgres_data`
- `redis_data`
- `model_artifacts`
- `chroma_data`
- `qdrant_data`

### Why both `chroma_data` and `qdrant_data` still exist
- `qdrant_data` is active runtime persistence
- `chroma_data` is kept for rollback / migration / local fallback

## 10. Local Bootstrap Order

Recommended order after fresh start:

```bash
docker compose up -d --build
docker compose exec -T backend alembic upgrade head
curl -X POST http://localhost:8001/api/admin/train -H "X-Api-Key: $API_KEY_ADMIN"
curl -X POST http://localhost:8001/api/knowledge/ingest-reports -H "X-Api-Key: $API_KEY_ADMIN"
docker compose --profile tools run --rm cache-warmup
```

PowerShell variant with the admin key read from the running backend container:

```powershell
$env:QDRANT_HOST_PORT='6337'
docker compose up -d --build
docker compose exec -T backend alembic upgrade head
$apiKey = (docker compose exec -T backend printenv API_KEY_ADMIN).Trim()
curl.exe -fsS http://localhost:8001/api/health
curl.exe -fsS http://localhost:6337/readyz
curl.exe -fsS -X POST http://localhost:8001/api/admin/train -H "X-Api-Key: $apiKey"
curl.exe -fsS -X POST http://localhost:8001/api/knowledge/ingest-reports -H "X-Api-Key: $apiKey"
docker compose --profile tools run --rm cache-warmup
```

### What each step does
- `alembic upgrade head`: DB schema, including trace tables
- `train`: creates active forecasting model artifact
- `ingest-reports`: generates product/category reports and stores vectors
- `cache-warmup`: warms 40 preset questions and locale variants

### Qdrant-specific note
- the official `qdrant/qdrant` image is slim and does not include `curl` or `wget`
- local and production Compose healthchecks therefore use a PID 1 liveness check instead of HTTP probing inside the container
- external smoke tests should still verify `http://localhost:<QDRANT_HOST_PORT>/readyz`

## 11. Production Deploy Model

### GitHub Actions

#### Build images
- workflow: [images.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/.github/workflows/images.yml)
- builds:
  - backend image
  - frontend image
- pushes both to GHCR

#### Deploy
- workflow: [deploy.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/.github/workflows/deploy.yml)
- trigger: successful `Build & Push Images`
- server action:
  - upload `docker-compose.prod.yml`
  - `docker compose pull`
  - `docker compose up -d --force-recreate --remove-orphans`
  - `alembic upgrade head`

#### Bootstrap
- workflow: [bootstrap.yml](/c:/Users/lukas/Desktop/PYTHON_PROJECTS_DESKTOP/PYTHON_PROJECTS/ai-enterprise-intelligence/.github/workflows/bootstrap.yml)
- manual trigger
- optional actions:
  - train model
  - ingest reports
  - warm preset cache
  - flush preset cache before warmup

## 12. Server Requirements

Required on server:
- Docker
- Docker Compose plugin
- project `.env` in app dir
- SSH access from GitHub Actions
- GHCR pull access if repository is private

### GitHub Actions secrets / variables
- `SERVER_HOST`
- `SERVER_USER`
- `SERVER_SSH_KEY`
- `NEXT_PUBLIC_API_URL` for frontend build

## 13. Qdrant Migration Plan

### Current code state
- runtime supports both `Chroma` and `Qdrant`
- Docker runtime is already set to `Qdrant`
- migration script exists

### If you already have Chroma data and want to migrate

```bash
cd backend
python -m scripts.migrate_chroma_to_qdrant
```

What it migrates:
- main RAG collection
- assistant semantic cache collection

### If you want a fully clean rebuild instead of migration

```bash
curl -X POST http://localhost:8001/api/knowledge/reset -H "X-Api-Key: $API_KEY_ADMIN"
curl -X POST http://localhost:8001/api/knowledge/ingest-reports -H "X-Api-Key: $API_KEY_ADMIN"
docker compose --profile tools run --rm cache-warmup
```

### Rollback to Chroma

Set:

```env
VECTORSTORE=chroma
ASSISTANTS_SEMANTIC_CACHE_BACKEND=chroma
```

Then recreate backend.

## 14. Redis Cache Behavior

### Preset cache
- Redis keyspace for preset answers
- locale-aware
- no expiry by default
- used for presentation/demo speed and token saving

### Custom exact cache
- keyed by normalized raw query hash
- Redis

### Semantic cache
- vector-backed
- backend is pluggable
- used only for custom assistant questions

### Deterministic facts cache
- Redis
- keyed by canonical spec hash + data fingerprint

## 15. Knowledge RAG Retrieval Notes

### Search parameter inference
`KnowledgeService` chooses `k` and optional filter by query type:
- product-specific question
- category question
- cross-product ranking context
- comparison context

### Important limitation
Knowledge RAG is still intended for:
- trends
- report-style explanations
- factual summaries from report documents

It is not the source of truth for exact top/bottom numeric business questions anymore.

## 16. Testing

### Main backend test command

```bash
cd backend
pytest
```

### Focused assistant/vector test command

```bash
cd backend
pytest tests/test_assistants_service.py \
       tests/test_assistants_facts_mapper.py \
       tests/test_assistants_facts_service.py \
       tests/test_assistants_cache.py \
       tests/test_assistants_query_cache.py \
       tests/test_assistants_semantic_policy.py \
       tests/test_assistants_trace_recorder.py \
       tests/test_rag.py
```

### Extra syntax check

```bash
cd backend
python -m compileall app scripts
```

## 17. Useful Dev Commands

### Logs

```bash
docker compose logs backend --tail=200
docker compose logs qdrant --tail=200
docker compose logs redis --tail=200
```

### Check assistant trace tables

```bash
docker compose exec -T postgres psql -U postgres -d retail_forecast -c "\dt assistant_*"
```

### Check Redis size

```bash
docker compose exec -T redis redis-cli DBSIZE
```

### Check active products

```bash
curl http://localhost:8001/api/data/products
```

### Reset and re-ingest active RAG backend

```bash
cd backend
python -m scripts.rag_reset_and_ingest
```

## 18. Current Known Constraints

### Qdrant migration is code-complete but not yet pushed
- local repo can run with Qdrant now
- server rollout still depends on next push/deploy cycle

### Some old docs still mention Chroma as main backend
- `README.md` reflects older state
- `README.dev.md` reflects current state

### Frontend production build on local Windows
- there was an existing Next/CSS loader Windows ESM issue before this work
- backend and tests are the source of truth for validation here

## 19. Recommended Next Steps

1. Commit and review the Qdrant migration.
2. Start local Docker stack and verify Qdrant health.
3. Run bootstrap flow:
   `train -> ingest-reports -> warm_preset_cache`
4. Verify:
   - forecast works
   - preset cache works
   - deterministic facts answers are stable
   - traces are visible
5. Push only after local smoke test.

## 20. Smoke Test Checklist

### Exact local smoke test that was verified

PowerShell:

```powershell
$env:QDRANT_HOST_PORT='6337'
docker compose up -d --build
docker compose exec -T backend alembic upgrade head
curl.exe -fsS http://localhost:8001/api/health
curl.exe -fsS http://localhost:6337/readyz
$apiKey = (docker compose exec -T backend printenv API_KEY_ADMIN).Trim()
curl.exe -fsS -X POST http://localhost:8001/api/admin/train -H "X-Api-Key: $apiKey"
curl.exe -fsS -X POST http://localhost:8001/api/knowledge/ingest-reports -H "X-Api-Key: $apiKey"
docker compose --profile tools run --rm cache-warmup
docker compose exec -T redis redis-cli DBSIZE
curl.exe -fsS -X POST http://localhost:8001/api/assistants/ask-preset -H "Content-Type: application/json" -d '{"assistant_type":"knowledge","question_id":"k_001","locale":"cs"}'
curl.exe -fsS -X POST http://localhost:8001/api/assistants/ask-custom -H "Content-Type: application/json" -d '{"assistant_type":"knowledge","query":"Který produkt se prodává nejvíc?","locale":"cs"}'
curl.exe -fsS -X POST http://localhost:8001/api/assistants/ask-custom -H "Content-Type: application/json" -d '{"assistant_type":"knowledge","query":"Jaký je nejprodávanější produkt?","locale":"cs"}'
```

Expected outcomes:
- backend health returns `status=ok`
- Qdrant `readyz` returns `all shards are ready`
- preset response returns `"cached": true`
- deterministic facts responses return the same product for equivalent Czech paraphrases
- repeated equivalent fact questions return `"cache_source":"deterministic_facts_cache"` in `trace_summary`

### Forecast
- load forecast for `P0001`
- confirm trained model exists

### Presets
- click multiple preset questions
- confirm fast answers
- confirm Redis keys persist after Redis restart

### Deterministic facts
- ask equivalent questions:
  - `Který produkt se prodává nejvíc?`
  - `Jaký je nejprodávanější produkt?`
  - `Který produkt má nejvyšší počet prodaných kusů?`
- expect same answer

### Traces
- open response trace
- verify route:
  - `deterministic_facts` for exact supported business fact
  - `default_assistant` for normal RAG/analyst questions

## 21. Commit Discipline

Do not include in commits unless explicitly intended:
- `.claude/`
- `retail_forecast.sql`
- local secrets
- generated local artifacts

Current recommended workflow:
1. implement locally
2. run focused tests
3. commit
4. push only when runtime is verified
