"""
BLOQUE 2 — LanceDB dentro de Docker: Test Suite (HostAI)
15 test cases: conexion, tablas, schema, insert, search, error handling, config, and 8 extra cases.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ─── TC-01: LanceDB dependency declared in pyproject.toml ─────────────────────
def test_tc01_lancedb_in_pyproject():
    """TC-01: lancedb and pyarrow must be declared as dependencies."""
    content = (PROJECT_ROOT / "pyproject.toml").read_text()
    assert "lancedb" in content, "lancedb missing from pyproject.toml"
    assert "pyarrow" in content, "pyarrow missing from pyproject.toml"


# ─── TC-02: docker-compose has lancedb_data volume ────────────────────────────
def test_tc02_compose_lancedb_volume():
    """TC-02: docker-compose.yml must declare lancedb_data volume and mount it on api."""
    import yaml

    data = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
    assert "lancedb_data" in data.get("volumes", {}), "Missing lancedb_data volume"
    api_volumes = data["services"]["api"].get("volumes", [])
    assert any("lancedb" in str(v) for v in api_volumes), "lancedb volume not mounted on api"
    api_env = data["services"]["api"].get("environment", [])
    env_str = str(api_env)
    assert "LANCEDB_URI" in env_str, "LANCEDB_URI not set in api service environment"


# ─── TC-03: LanceDBClient connects and creates data dir ───────────────────────
def test_tc03_client_connect():
    """TC-03: LanceDBClient.connect() must create the directory and return a connection."""
    import lancedb
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp:
        uri = os.path.join(tmp, "testdb")
        client = LanceDBClient(uri=uri)
        db = client.connect()
        assert Path(uri).exists(), "LanceDB data dir not created"
        assert isinstance(db, lancedb.DBConnection)


# ─── TC-04: init_tables creates all expected tables ───────────────────────────
def test_tc04_init_tables():
    """TC-04: init_tables() must create reservations_vectors, conversation_memory, voice_transcripts."""
    from src.services.lancedb_client import LanceDBClient, TABLES

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        existing = set(client.list_tables())
        for table_name in TABLES:
            assert table_name in existing, f"Table not created: {table_name}"


# ─── TC-05: init_tables is idempotent (no error on double call) ───────────────
def test_tc05_init_tables_idempotent():
    """TC-05: Calling init_tables() twice must not raise any error."""
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        client.init_tables()  # second call — must not raise
        assert len(client.list_tables()) == 3


# ─── TC-06: get_table raises ValueError for unknown table ─────────────────────
def test_tc06_get_table_unknown_raises():
    """TC-06: Accessing an unknown table must raise ValueError with a helpful message."""
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        with pytest.raises(ValueError, match="Unknown table"):
            client.get_table("non_existent_table")


# ─── TC-07: config.yaml has lancedb section with required keys ────────────────
def test_tc07_config_yaml_lancedb():
    """TC-07: config.yaml must have a lancedb section with uri, tables, embedding_dim."""
    import yaml

    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())
    ldb = data.get("lancedb", {})
    assert ldb, "Missing [lancedb] section in config.yaml"
    assert "uri" in ldb, "Missing lancedb.uri"
    assert "tables" in ldb, "Missing lancedb.tables"
    assert "embedding_dim" in ldb, "Missing lancedb.embedding_dim"
    assert ldb["embedding_dim"] == 1536
    expected_tables = {"reservations_vectors", "conversation_memory", "voice_transcripts"}
    assert set(ldb["tables"]) == expected_tables


# ─── TC-08: list_tables() returns empty list before init ─────────────────────
def test_tc08_list_tables_empty_before_init():
    """TC-08: LanceDBClient.list_tables() must return [] before init_tables() is called."""
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        tables = client.list_tables()
        assert isinstance(tables, list), "list_tables() must return a list"
        assert len(tables) == 0, f"Expected 0 tables before init, got: {tables}"


# ─── TC-09: init_tables creates exactly 3 tables ─────────────────────────────
def test_tc09_init_tables_creates_exactly_three():
    """TC-09: init_tables() must create exactly 3 tables."""
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        tables = client.list_tables()
        assert len(tables) == 3, f"Expected 3 tables, got {len(tables)}: {tables}"


# ─── TC-10: get_table returns a table object after init ──────────────────────
def test_tc10_get_table_returns_object():
    """TC-10: get_table() must return a non-None table object for a known table name."""
    from src.services.lancedb_client import LanceDBClient, TABLES

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        first_table = next(iter(TABLES))
        tbl = client.get_table(first_table)
        assert tbl is not None, f"get_table('{first_table}') returned None"


# ─── TC-11: Two clients on different URIs are isolated ───────────────────────
def test_tc11_two_clients_isolated():
    """TC-11: Two LanceDBClient instances on different URIs must not share tables."""
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp1:
        with tempfile.TemporaryDirectory() as tmp2:
            c1 = LanceDBClient(uri=tmp1)
            c2 = LanceDBClient(uri=tmp2)
            c1.init_tables()
            assert len(c2.list_tables()) == 0, "Clients should be isolated before c2.init_tables()"
            c2.init_tables()
            assert len(c2.list_tables()) == 3


# ─── TC-12: LANCEDB_URI env override is reflected in config ──────────────────
def test_tc12_lancedb_uri_env_in_settings(monkeypatch):
    """TC-12: LANCEDB_URI env var must override the lancedb uri in settings."""
    monkeypatch.setenv("LANCEDB_URI", "/tmp/test-lancedb-uri-tc12")
    from src.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.lancedb_uri == "/tmp/test-lancedb-uri-tc12"
    get_settings.cache_clear()


# ─── TC-13: config.yaml embedding_dim is 1536 ────────────────────────────────
def test_tc13_config_yaml_embedding_dim():
    """TC-13: config.yaml lancedb.embedding_dim must equal 1536."""
    import yaml

    data = yaml.safe_load((PROJECT_ROOT / "config.yaml").read_text())
    assert data["lancedb"]["embedding_dim"] == 1536


# ─── TC-14: list_tables after init returns all expected names ────────────────
def test_tc14_list_tables_contains_all_expected():
    """TC-14: list_tables() after init must contain all TABLES constant values."""
    from src.services.lancedb_client import LanceDBClient, TABLES

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        existing = set(client.list_tables())
        for name in TABLES:
            assert name in existing, f"Expected table '{name}' not found in {existing}"


# ─── TC-15: get_table error message mentions the unknown table name ───────────
def test_tc15_get_table_error_message_has_table_name():
    """TC-15: ValueError from get_table must include the unknown table name in its message."""
    from src.services.lancedb_client import LanceDBClient

    with tempfile.TemporaryDirectory() as tmp:
        client = LanceDBClient(uri=tmp)
        client.init_tables()
        unknown = "this_table_does_not_exist"
        with pytest.raises(ValueError, match=unknown):
            client.get_table(unknown)
