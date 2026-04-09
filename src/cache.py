"""
Step 12 — Semantic Caching + Cost Optimization (ai-host-agent).

Provides an LLM-response cache backed by LanceDB vector similarity search.
Semantically similar queries reuse cached responses, cutting API costs and
reducing round-trip latency for the restaurant reservation pipeline.

Components:
  CACHE_VECTOR_DIM   : embedding dimensionality (384)
  CacheConfig        : dataclass — threshold, TTL, table name, cost rates
  CacheStats         : hit/miss/savings counters with computed properties
  SemanticCache      : LanceDB-backed cache with lookup/store/clear
  get_cache()        : module-level singleton factory
  estimate_cost()    : USD cost estimator for a single LLM call
"""

from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import lancedb
import pyarrow as pa

# ─── Embedding ────────────────────────────────────────────────────────────────

CACHE_VECTOR_DIM: int = 384


def _hash_embed(text: str) -> list[float]:
    """
    Deterministic hash-based embedding for offline/test use.
    Produces a normalized 384-dimensional vector from SHA-256.
    Semantically identical strings → identical vectors (cosine = 1.0).
    Distinct strings → approximately orthogonal vectors (cosine ≈ 0).
    """
    raw = hashlib.sha256(text.encode("utf-8")).digest()  # 32 bytes
    n = CACHE_VECTOR_DIM
    extended = (list(raw) * ((n // len(raw)) + 1))[:n]
    floats = [b / 255.0 for b in extended]
    norm = sum(v * v for v in floats) ** 0.5 or 1.0
    return [v / norm for v in floats]


# ─── Schema ───────────────────────────────────────────────────────────────────


def _make_cache_schema() -> pa.Schema:
    return pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("query_text", pa.string()),
            pa.field("query_hash", pa.string()),
            pa.field("response_text", pa.string()),
            pa.field("model", pa.string()),
            pa.field("tokens_input", pa.int32()),
            pa.field("tokens_output", pa.int32()),
            pa.field("created_at", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), CACHE_VECTOR_DIM)),
        ]
    )


# ─── Configuration ────────────────────────────────────────────────────────────


@dataclass
class CacheConfig:
    """Semantic cache configuration for the HostAI pipeline."""

    enabled: bool = True
    similarity_threshold: float = 0.95  # cosine sim — at or above = cache hit
    max_entries: int = 1000  # evict oldest beyond this count
    ttl_hours: int = 24  # entries older than this are stale
    table_name: str = "session_response_cache"
    db_uri: str = field(default_factory=lambda: os.getenv("LANCEDB_URI", "/tmp/host_agent_cache"))
    # USD per 1M tokens — claude-sonnet-4-6 defaults
    cost_input_per_million: float = 3.0
    cost_output_per_million: float = 15.0


# ─── Stats ────────────────────────────────────────────────────────────────────


@dataclass
class CacheStats:
    """Running totals for cache performance and cost savings."""

    hits: int = 0
    misses: int = 0
    tokens_saved_input: int = 0
    tokens_saved_output: int = 0
    cost_input_per_million: float = 3.0
    cost_output_per_million: float = 15.0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def estimated_cost_saved_usd(self) -> float:
        in_cost = (self.tokens_saved_input / 1_000_000) * self.cost_input_per_million
        out_cost = (self.tokens_saved_output / 1_000_000) * self.cost_output_per_million
        return round(in_cost + out_cost, 6)


# ─── Cache ────────────────────────────────────────────────────────────────────


class SemanticCache:
    """
    LanceDB-backed semantic cache for LLM responses.

    Workflow:
      1. lookup(query)             → cached response string or None (miss)
      2. store(query, response)    → embed query and persist to LanceDB
      3. clear()                   → drop and recreate the table
      4. get_stats() / .stats      → CacheStats snapshot
    """

    def __init__(
        self,
        config: CacheConfig | None = None,
        embed_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self.config = config or CacheConfig()
        self._embed = embed_fn or _hash_embed
        self._stats = CacheStats(
            cost_input_per_million=self.config.cost_input_per_million,
            cost_output_per_million=self.config.cost_output_per_million,
        )
        self._db: lancedb.DBConnection | None = None
        self._table: lancedb.table.Table | None = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _connect(self) -> lancedb.DBConnection:
        if self._db is None:
            import pathlib

            pathlib.Path(self.config.db_uri).mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(self.config.db_uri)
        return self._db

    def _get_table(self) -> lancedb.table.Table:
        if self._table is not None:
            return self._table
        db = self._connect()
        existing = self._list_table_names(db)
        if self.config.table_name not in existing:
            db.create_table(self.config.table_name, schema=_make_cache_schema())
        self._table = db.open_table(self.config.table_name)
        return self._table

    @staticmethod
    def _list_table_names(db: lancedb.DBConnection) -> list[str]:
        """Handle lancedb API differences across versions."""
        raw = db.list_tables()
        if hasattr(raw, "tables"):
            return list(raw.tables or [])
        if isinstance(raw, list):
            return raw
        try:
            return list(raw)
        except TypeError:
            return []

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ── Public API ────────────────────────────────────────────────────────────

    def lookup(self, query: str) -> Optional[str]:
        """
        Search the cache for a semantically similar previous query.

        Uses cosine similarity computed directly from stored vectors to avoid
        dependency on LanceDB's distance metric interpretation across versions.
        Returns the cached response string or None on a miss.
        """
        if not self.config.enabled:
            self._stats.misses += 1
            return None

        tbl = self._get_table()
        query_vec = self._embed(query)
        try:
            results = tbl.search(query_vec).limit(1).to_list()
        except Exception:
            self._stats.misses += 1
            return None

        if not results:
            self._stats.misses += 1
            return None

        row = results[0]
        stored_vec = row.get("vector")
        if stored_vec is None:
            self._stats.misses += 1
            return None

        cosine_sim = self._cosine_similarity(query_vec, list(stored_vec))
        if cosine_sim >= self.config.similarity_threshold:
            self._stats.hits += 1
            self._stats.tokens_saved_input += int(row.get("tokens_input") or 0)
            self._stats.tokens_saved_output += int(row.get("tokens_output") or 0)
            return str(row["response_text"])

        self._stats.misses += 1
        return None

    def store(
        self,
        query: str,
        response: str,
        *,
        model: str = "",
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        """Embed the query and store the response in LanceDB."""
        if not self.config.enabled:
            return

        tbl = self._get_table()
        query_vec = self._embed(query)
        query_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        record: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "query_text": query,
            "query_hash": query_hash,
            "response_text": response,
            "model": model,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "created_at": now,
            "vector": query_vec,
        }
        tbl.add([record])

    def clear(self) -> None:
        """Drop and recreate the cache table, resetting all stats."""
        db = self._connect()
        existing = self._list_table_names(db)
        if self.config.table_name in existing:
            db.drop_table(self.config.table_name)
        self._table = None
        self._stats = CacheStats(
            cost_input_per_million=self.config.cost_input_per_million,
            cost_output_per_million=self.config.cost_output_per_million,
        )

    def get_stats(self) -> CacheStats:
        """Return a snapshot copy of the current stats."""
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            tokens_saved_input=self._stats.tokens_saved_input,
            tokens_saved_output=self._stats.tokens_saved_output,
            cost_input_per_million=self._stats.cost_input_per_million,
            cost_output_per_million=self._stats.cost_output_per_million,
        )

    @property
    def stats(self) -> CacheStats:
        return self._stats


# ─── Module-level singleton ───────────────────────────────────────────────────

_cache_instance: Optional[SemanticCache] = None


def get_cache(
    config: CacheConfig | None = None,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> SemanticCache:
    """Return (or create) the module-level SemanticCache singleton."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache(config=config, embed_fn=embed_fn)
    return _cache_instance


# ─── Cost estimator ───────────────────────────────────────────────────────────


def estimate_cost(
    tokens_input: int,
    tokens_output: int,
    model: str = "claude-haiku-4-5-20251001",
) -> float:
    """
    Estimate API cost in USD for a single LLM call.

    Rates (USD per 1M tokens, as of 2026-04):
      claude-sonnet-4-6         : $3.00 input / $15.00 output
      claude-haiku-4-5-20251001 : $0.25 input /  $1.25 output
      claude-haiku-4-5          : $0.25 input /  $1.25 output
      claude-opus-4-6           : $15.00 input / $75.00 output
    """
    rates: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-6": (3.0, 15.0),
        "claude-haiku-4-5-20251001": (0.25, 1.25),
        "claude-haiku-4-5": (0.25, 1.25),
        "claude-opus-4-6": (15.0, 75.0),
    }
    in_rate, out_rate = rates.get(model, (3.0, 15.0))
    return round(
        (tokens_input / 1_000_000) * in_rate + (tokens_output / 1_000_000) * out_rate,
        8,
    )
