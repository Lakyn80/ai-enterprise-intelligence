"""FastAPI app factory - entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import get_logger, setup_logging
from app.forecasting.router import router as forecasting_router
from app.ai_assistant.router import router as assistant_router
from app.knowledge_rag.router import router as knowledge_router
from app.settings import settings

logger = get_logger(__name__)

# In-memory metrics (modular, can be replaced with Prometheus)
_metrics: dict[str, int] = {
    "requests_total": 0,
    "forecast_requests": 0,
    "assistant_requests": 0,
    "knowledge_queries": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("Application starting", extra={"rag_enabled": settings.rag_enabled})
    yield
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Retail Forecast API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "service": "retail-forecast-api"}

    @app.get("/api/metrics")
    async def metrics():
        return _metrics

    app.include_router(forecasting_router)
    app.include_router(assistant_router)
    if settings.rag_enabled:
        app.include_router(knowledge_router)

    return app
