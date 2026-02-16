"""
API Key authentication dependency.

When API_SECRET_KEY is set, all protected endpoints require the header:
    X-API-Key: <your-key>
    or
    Authorization: Bearer <your-key>

When API_SECRET_KEY is empty (development), auth is bypassed.
"""

import logging
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency that enforces API key authentication.

    Skipped when API_SECRET_KEY is not configured (dev mode).
    """
    # If no secret key configured, skip auth (development mode)
    if not settings.api_secret_key:
        return ""

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if api_key != settings.api_secret_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
