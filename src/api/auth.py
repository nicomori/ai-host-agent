"""
Authentication — HostAI (ai-host-agent).
Accepts X-API-Key header OR Bearer JWT token (from /api/v1/auth/token).
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from src.config import get_settings

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ha-jwt-secret-2026-changeme")
ALGORITHM = "HS256"


async def verify_api_key(
    request: Request,
    api_key: Optional[str] = Security(_API_KEY_HEADER),
) -> str:
    """Accept X-API-Key header or Bearer JWT token."""
    cfg = get_settings()

    # Form 1: API key header
    if api_key and api_key == cfg.api_key:
        return api_key

    # Form 2: Bearer JWT token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            from jose import jwt

            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub", "unknown")
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
