"""API key authentication for admin endpoints."""

from fastapi import Header, HTTPException, status

from app.settings import settings


async def verify_api_key(x_api_key: str | None = Header(None)) -> str:
    """Verify API key for admin endpoints."""
    if not x_api_key or x_api_key != settings.api_key_admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
