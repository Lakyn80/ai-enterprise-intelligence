"""Pytest configuration and fixtures."""

import os

# Ensure test env - use PostgreSQL URL for real DB; tests may skip if unavailable
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/retail_forecast_test")
os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://postgres:postgres@localhost:5433/retail_forecast_test")
os.environ.setdefault("API_KEY_ADMIN", "test-key")
os.environ.setdefault("RAG_ENABLED", "false")
