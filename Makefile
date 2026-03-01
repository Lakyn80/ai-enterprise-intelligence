.PHONY: up down seed train test

up:
	docker compose up -d

down:
	docker compose down

import-kaggle:
	docker compose exec backend curl -s -X POST "http://localhost:8000/api/admin/import-kaggle" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}"

seed:
	docker compose exec backend curl -s -X POST "http://localhost:8000/api/admin/seed" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}"

train:
	docker compose exec backend curl -s -X POST "http://localhost:8000/api/admin/train?from_date=2024-01-01&to_date=2025-03-31" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}"

test:
	cd backend && pytest tests/ -v

rag-reset:
	docker compose exec backend curl -s -X POST "http://localhost:8000/api/knowledge/reset" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}"

rag-ingest:
	docker compose exec backend curl -s -X POST "http://localhost:8000/api/knowledge/ingest" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}" \
		-H "Content-Type: application/json" \
		-d '{"folder_path": "/data/knowledge"}'

kaggle-download:
	docker compose run --rm -v "$(PWD)/data:/data" -v "$(HOME)/.kaggle:/root/.kaggle:ro" -w /data backend sh -c " \
		kaggle datasets download -d anirudhchauhan/retail-store-inventory-forecasting-dataset && \
		(unzip -o retail-store-inventory-forecasting-dataset.zip 2>/dev/null || python -m zipfile -e retail-store-inventory-forecasting-dataset.zip .) && \
		ls -la"
