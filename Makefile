.PHONY: up down seed train test

up:
	docker compose up -d

down:
	docker compose down

seed:
	curl -X POST "http://localhost:8000/api/admin/seed" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}"

train:
	curl -X POST "http://localhost:8000/api/admin/train?from_date=2024-01-01&to_date=2025-03-31" \
		-H "X-Api-Key: $${API_KEY_ADMIN:-dev-admin-key-change-in-production}"

test:
	cd backend && pytest tests/ -v
