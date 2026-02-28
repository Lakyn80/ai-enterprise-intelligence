"""Dependency injection wiring for FastAPI."""

from typing import Annotated

from fastapi import Depends

from app.core.security import verify_api_key
from app.db.session import AsyncSessionDep

# Re-export for convenience
ApiKeyDep = Annotated[str, Depends(verify_api_key)]
