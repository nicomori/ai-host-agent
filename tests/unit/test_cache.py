"""
Step 12 — Semantic Caching + Cost Optimization tests (ai-host-agent).

7 test cases:
  TC1: CacheConfig has correct defaults
  TC2: CacheStats computed properties (hit_rate, estimated_cost_saved_usd)
  TC3: lookup() returns None when cache is empty (miss)
  TC4: store() + lookup() same query → cache hit, returns cached response
  TC5: lookup() returns None for a dissimilar query (cosine below threshold)
  TC6: CacheStats tracks hits and misses correctly across multiple calls
  TC7: clear() empties the cache — subsequent lookup returns None
"""

from __future__ import annotations

import pytest

from src.cache import (
    CACHE_VECTOR_DIM,
    CacheConfig,
    CacheStats,
    SemanticCache,
    _hash_embed,
    estimate_cost,
    get_cache,
)

import src.cache as cache_module


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_orthogonal_embed():
    """
    Returns an embed_fn that produces orthogonal unit vectors for different
    categories of text, giving full control over cosine similarity in tests.
    """
    dim = CACHE_VECTOR_DIM

    def embed(text: str) -> list[float]:
        # All "reservation" queries → same first basis vector (cosine = 1.0 between them)
        # All "cancel" queries → second basis vector (cosine = 0.0 vs reservation)
        v = [0.0] * dim
        if "reservation" in text.lower() or "book" in text.lower():
            v[0] = 1.0
        elif "cancel" in text.lower():
            v[1] = 1.0
        else:
            v[2] = 1.0
        return v

    return embed


@pytest.fixture
def tmp_cache(tmp_path):
    """Isolated SemanticCache in a temporary directory."""
    config = CacheConfig(
        db_uri=str(tmp_path / "test_cache_db"),
        table_name="test_session_cache",
        similarity_threshold=0.95,
    )
    return SemanticCache(config=config, embed_fn=_hash_embed)


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    """Reset the module-level singleton before and after each test."""
    original = cache_module._cache_instance
    cache_module._cache_instance = None
    yield
    cache_module._cache_instance = original


# ══════════════════════════════════════════════════════════════════════════════
# TC1 — CacheConfig defaults
# ══════════════════════════════════════════════════════════════════════════════


def test_tc1_cache_config_defaults():
    """CacheConfig must have sensible defaults for the HostAI pipeline."""
    config = CacheConfig()
    print(f"\nTC1 CacheConfig: {config}")
    assert config.enabled is True
    assert config.similarity_threshold == 0.95
    assert config.max_entries == 1000
    assert config.ttl_hours == 24
    assert config.table_name == "session_response_cache"
    assert config.cost_input_per_million == 3.0
    assert config.cost_output_per_million == 15.0


def test_tc1_cache_config_custom():
    """CacheConfig must accept custom overrides."""
    config = CacheConfig(
        enabled=False,
        similarity_threshold=0.99,
        table_name="custom_cache",
        cost_input_per_million=0.25,
    )
    assert config.enabled is False
    assert config.similarity_threshold == 0.99
    assert config.table_name == "custom_cache"
    assert config.cost_input_per_million == 0.25


# ══════════════════════════════════════════════════════════════════════════════
# TC2 — CacheStats computed properties
# ══════════════════════════════════════════════════════════════════════════════


def test_tc2_cache_stats_zero_state():
    """CacheStats with no calls must have hit_rate=0 and cost_saved=0."""
    stats = CacheStats()
    print(f"\nTC2 CacheStats zero: hits={stats.hits} misses={stats.misses}")
    assert stats.total_requests == 0
    assert stats.hit_rate == 0.0
    assert stats.estimated_cost_saved_usd == 0.0


def test_tc2_cache_stats_hit_rate():
    """hit_rate must equal hits / total_requests."""
    stats = CacheStats(hits=3, misses=1)
    assert stats.total_requests == 4
    assert stats.hit_rate == 0.75


def test_tc2_cache_stats_cost_saved():
    """estimated_cost_saved_usd must reflect token savings and configured rates."""
    stats = CacheStats(
        hits=1,
        tokens_saved_input=1_000_000,  # 1M input tokens
        tokens_saved_output=500_000,  # 0.5M output tokens
        cost_input_per_million=3.0,
        cost_output_per_million=15.0,
    )
    # 1M * 3.0 + 0.5M * 15.0 = 3.0 + 7.5 = 10.5
    assert stats.estimated_cost_saved_usd == 10.5
    print(f"\nTC2 cost_saved: ${stats.estimated_cost_saved_usd}")


# ══════════════════════════════════════════════════════════════════════════════
# TC3 — lookup() returns None when cache is empty
# ══════════════════════════════════════════════════════════════════════════════


def test_tc3_lookup_miss_empty_cache(tmp_cache):
    """lookup() must return None when no entries exist in the cache."""
    result = tmp_cache.lookup("book a table for 4 people on Friday at 8pm")
    print(f"\nTC3 lookup empty cache: {result}")
    assert result is None
    assert tmp_cache.stats.misses == 1
    assert tmp_cache.stats.hits == 0


def test_tc3_lookup_disabled_cache(tmp_path):
    """When cache is disabled, lookup() must always return None (fast path)."""
    config = CacheConfig(
        enabled=False,
        db_uri=str(tmp_path / "disabled_db"),
        table_name="disabled_table",
    )
    cache = SemanticCache(config=config)
    result = cache.lookup("any query")
    assert result is None
    assert cache.stats.misses == 1


# ══════════════════════════════════════════════════════════════════════════════
# TC4 — store() + lookup() same query → cache hit
# ══════════════════════════════════════════════════════════════════════════════


def test_tc4_store_then_lookup_same_query(tmp_cache):
    """
    After storing a query-response pair, looking up the identical query must
    return the cached response and increment the hits counter.
    """
    query = "I need a reservation for 2 tonight at 7pm"
    response = "I've booked a table for 2 at 7pm. Confirmation: #HAG-001"

    tmp_cache.store(query, response, model="claude-sonnet-4-6", tokens_input=50, tokens_output=30)
    result = tmp_cache.lookup(query)

    print(f"\nTC4 cache hit result: {result!r}")
    assert result == response
    assert tmp_cache.stats.hits == 1
    assert tmp_cache.stats.misses == 0
    assert tmp_cache.stats.tokens_saved_input == 50
    assert tmp_cache.stats.tokens_saved_output == 30


def test_tc4_store_disabled_does_not_persist(tmp_path):
    """store() on a disabled cache must be a no-op — lookup still returns None."""
    config = CacheConfig(
        enabled=False,
        db_uri=str(tmp_path / "noop_db"),
        table_name="noop_table",
    )
    cache = SemanticCache(config=config)
    cache.store("hello", "world")
    # Re-enable and lookup — should be empty
    cache.config.enabled = True
    result = cache.lookup("hello")
    assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# TC5 — lookup() returns None for a dissimilar query
# ══════════════════════════════════════════════════════════════════════════════


def test_tc5_lookup_miss_dissimilar_query(tmp_path):
    """
    When the lookup query is semantically unrelated to the stored query,
    cosine similarity falls below the threshold and lookup() returns None.

    Uses orthogonal embed_fn to guarantee cosine = 0.0 between the two queries.
    """
    embed = _make_orthogonal_embed()
    config = CacheConfig(
        db_uri=str(tmp_path / "dissimilar_db"),
        table_name="dissimilar_cache",
        similarity_threshold=0.95,
    )
    cache = SemanticCache(config=config, embed_fn=embed)

    # Store: "book a reservation" → maps to basis vector [1, 0, 0, ...]
    cache.store(
        "book a reservation for Friday",
        "Table booked for Friday at 8pm",
        tokens_input=40,
        tokens_output=20,
    )

    # Lookup: "cancel" → maps to basis vector [0, 1, 0, ...] — cosine = 0.0
    result = cache.lookup("cancel my appointment")
    print(f"\nTC5 dissimilar miss: {result}")
    assert result is None
    assert cache.stats.misses == 1
    assert cache.stats.hits == 0


def test_tc5_lookup_hit_similar_query(tmp_path):
    """
    When two queries map to the same basis vector (cosine = 1.0), lookup hits.
    """
    embed = _make_orthogonal_embed()
    config = CacheConfig(
        db_uri=str(tmp_path / "similar_db"),
        table_name="similar_cache",
        similarity_threshold=0.95,
    )
    cache = SemanticCache(config=config, embed_fn=embed)

    cache.store("book a reservation for dinner", "Table reserved for dinner!")
    result = cache.lookup("I want to book a table tonight")  # also "book" → same basis vector
    assert result == "Table reserved for dinner!"
    assert cache.stats.hits == 1


# ══════════════════════════════════════════════════════════════════════════════
# TC6 — CacheStats tracks hits and misses correctly
# ══════════════════════════════════════════════════════════════════════════════


def test_tc6_stats_track_multiple_calls(tmp_path):
    """
    After a mix of cache hits and misses, CacheStats must accurately reflect
    all counts and derived metrics (hit_rate, cost saved).
    """
    embed = _make_orthogonal_embed()
    config = CacheConfig(
        db_uri=str(tmp_path / "stats_db"),
        table_name="stats_cache",
        similarity_threshold=0.95,
    )
    cache = SemanticCache(config=config, embed_fn=embed)

    # Store one entry
    cache.store(
        "book a reservation",
        "Reservation confirmed!",
        tokens_input=100,
        tokens_output=50,
    )

    # 2 hits (same query → same basis vector)
    cache.lookup("book a table tonight")
    cache.lookup("book a reservation now")
    # 1 miss (different category — no "book" or "reservation" in text)
    cache.lookup("cancel my plans for tonight")

    stats = cache.get_stats()
    print(f"\nTC6 stats: hits={stats.hits} misses={stats.misses} rate={stats.hit_rate:.2f}")
    assert stats.hits == 2
    assert stats.misses == 1
    assert stats.total_requests == 3
    assert abs(stats.hit_rate - 2 / 3) < 1e-9
    assert stats.tokens_saved_input == 200  # 2 hits × 100 tokens
    assert stats.tokens_saved_output == 100  # 2 hits × 50 tokens
    assert stats.estimated_cost_saved_usd > 0.0


# ══════════════════════════════════════════════════════════════════════════════
# TC7 — clear() empties the cache
# ══════════════════════════════════════════════════════════════════════════════


def test_tc7_clear_empties_cache(tmp_cache):
    """
    After clear(), the cache must be empty: lookup() returns None and
    stats are reset to zero.
    """
    query = "book a table for 6 this weekend"
    response = "Table booked! Confirmation #HAG-007"

    tmp_cache.store(query, response)
    assert tmp_cache.lookup(query) == response  # warm the cache

    tmp_cache.clear()

    result_after_clear = tmp_cache.lookup(query)
    print(f"\nTC7 after clear: {result_after_clear}")
    assert result_after_clear is None
    # Stats reset on clear
    assert tmp_cache.stats.hits == 0
    assert tmp_cache.stats.misses == 1  # the lookup after clear
    assert tmp_cache.stats.tokens_saved_input == 0


def test_tc7_clear_then_reuse(tmp_cache):
    """After clear(), the cache must accept new entries normally."""
    tmp_cache.store("first query", "first response")
    tmp_cache.clear()
    tmp_cache.store("second query", "second response")
    assert tmp_cache.lookup("second query") == "second response"
    assert tmp_cache.stats.hits == 1


# ══════════════════════════════════════════════════════════════════════════════
# Extra — get_cache() singleton and estimate_cost()
# ══════════════════════════════════════════════════════════════════════════════


def test_get_cache_returns_singleton(tmp_path):
    """get_cache() must return the same instance on subsequent calls."""
    config = CacheConfig(db_uri=str(tmp_path / "singleton_db"))
    c1 = get_cache(config=config)
    c2 = get_cache()
    assert c1 is c2


def test_estimate_cost_sonnet():
    """estimate_cost with explicit sonnet model uses sonnet rates."""
    cost = estimate_cost(tokens_input=1_000_000, tokens_output=1_000_000, model="claude-sonnet-4-6")
    # $3.00 + $15.00 = $18.00
    assert cost == 18.0


def test_estimate_cost_default_is_haiku():
    """estimate_cost defaults to claude-haiku-4-5-20251001 rates."""
    cost = estimate_cost(tokens_input=1_000_000, tokens_output=1_000_000)
    # $0.25 + $1.25 = $1.50
    assert cost == 1.5


def test_estimate_cost_haiku():
    """estimate_cost must use claude-haiku-4-5 rates for haiku model."""
    cost = estimate_cost(
        tokens_input=1_000_000,
        tokens_output=1_000_000,
        model="claude-haiku-4-5-20251001",
    )
    # $0.25 + $1.25 = $1.50
    assert cost == 1.5


def test_estimate_cost_unknown_model_falls_back_to_sonnet():
    """Unknown model must fall back to sonnet rates."""
    cost = estimate_cost(tokens_input=1_000_000, tokens_output=0, model="unknown-model")
    assert cost == 3.0


def test_hash_embed_deterministic():
    """_hash_embed must produce identical vectors for identical strings."""
    v1 = _hash_embed("book a table")
    v2 = _hash_embed("book a table")
    assert v1 == v2
    assert len(v1) == CACHE_VECTOR_DIM


def test_hash_embed_distinct_strings():
    """_hash_embed must produce different vectors for different strings."""
    v1 = _hash_embed("book a table for 2")
    v2 = _hash_embed("cancel my reservation")
    assert v1 != v2
    # Cosine similarity between random-looking unit vectors should be < 0.5
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = sum(a * a for a in v1) ** 0.5
    norm_b = sum(b * b for b in v2) ** 0.5
    cosine = dot / (norm_a * norm_b)
    print(f"\nHash embed cosine (distinct): {cosine:.4f}")
    # Key property: cosine must be below the cache hit threshold (0.95)
    assert cosine < 0.95
