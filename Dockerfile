# ─── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache-dir \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.7.0" \
    "pydantic-settings>=2.3.0" \
    "httpx>=0.27.0" \
    "aiofiles>=23.2.1" \
    "anthropic>=0.29.0" \
    "langgraph>=0.2.0" \
    "langgraph-checkpoint-sqlite>=2.0.0" \
    "langchain-anthropic>=0.1.0" \
    "openai>=1.35.0" \
    "elevenlabs>=1.0.0" \
    "twilio>=9.0.0" \
    "asyncpg>=0.29.0" \
    "psycopg2-binary>=2.9.0" \
    "redis>=5.0.0" \
    "lancedb>=0.10.0" \
    "pyarrow>=15.0.0" \
    "tenacity>=8.3.0" \
    "structlog>=24.2.0" \
    "pyyaml>=6.0.1" \
    "python-dotenv>=1.0.1" \
    "apscheduler>=3.10.4" \
    "bcrypt>=4.1.0" \
    "python-jose[cryptography]>=3.3.0" \
    "pytest>=8.2.0" \
    "pytest-asyncio>=0.23.0" \
    "pytest-cov>=5.0.0" \
    "respx>=0.21.0" \
    "factory-boy>=3.3.0" \
    "ruff>=0.4.0" \
    "langfuse>=2.0.0" \
    "langchain>=0.2.0" \
    "python-multipart>=0.0.9"

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy full source
COPY . .

RUN mkdir -p /app/tmp/audio /app/tmp/transcripts

RUN useradd -r -s /bin/false appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
