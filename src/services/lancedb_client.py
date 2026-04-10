"""
LanceDB client — embedded vector store for HostAI.

Tables managed here:
  - reservations_vectors : semantic search over reservation history
  - conversation_memory  : per-session conversation chunks for context window
  - voice_transcripts    : indexed call transcripts
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa

# ─── Schema definitions ───────────────────────────────────────────────────────

RESERVATION_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("guest_name", pa.string()),
        pa.field("date", pa.string()),
        pa.field("party_size", pa.int32()),
        pa.field("status", pa.string()),
        pa.field("notes", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 1536)),
    ]
)

CONVERSATION_SCHEMA = pa.schema(
    [
        pa.field("session_id", pa.string()),
        pa.field("turn", pa.int32()),
        pa.field("role", pa.string()),
        pa.field("content", pa.string()),
        pa.field("timestamp", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 1536)),
    ]
)

TRANSCRIPT_SCHEMA = pa.schema(
    [
        pa.field("call_id", pa.string()),
        pa.field("reservation_id", pa.string()),
        pa.field("transcript", pa.string()),
        pa.field("duration_seconds", pa.float32()),
        pa.field("timestamp", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), 1536)),
    ]
)

# ─── Table registry ───────────────────────────────────────────────────────────

TABLES: dict[str, pa.Schema] = {
    "reservations_vectors": RESERVATION_SCHEMA,
    "conversation_memory": CONVERSATION_SCHEMA,
    "voice_transcripts": TRANSCRIPT_SCHEMA,
}


class LanceDBClient:
    """Thread-safe wrapper around lancedb.connect for HostAI."""

    def __init__(self, uri: str | None = None) -> None:
        self._uri = uri or os.environ.get("LANCEDB_URI", "/app/data/lancedb")
        self._db: lancedb.DBConnection | None = None

    def connect(self) -> lancedb.DBConnection:
        """Open (or reuse) connection to the local LanceDB store."""
        if self._db is None:
            Path(self._uri).mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(self._uri)
        return self._db

    def init_tables(self) -> None:
        """Idempotently create all tables if they don't already exist."""
        db = self.connect()
        existing = set(self.list_tables())  # use our wrapper — handles API differences
        for name, schema in TABLES.items():
            if name not in existing:
                db.create_table(name, schema=schema)

    def get_table(self, name: str) -> lancedb.table.Table:
        if name not in TABLES:
            raise ValueError(f"Unknown table: {name!r}. Valid: {list(TABLES)}")
        return self.connect().open_table(name)

    def table_exists(self, name: str) -> bool:
        return name in self.connect().table_names()

    def list_tables(self) -> list[str]:
        """Return table names. Handles lancedb API differences across versions.

        Resolution Form 1 (primary): response.tables attribute (lancedb >= 0.10 with namespace client)
        Resolution Form 2 (fallback): iterate/convert response object to list
        Resolution Form 3 (fallback): deprecated table_names() for older versions
        """
        raw = self.connect().list_tables()
        # Form 1: ListTablesResponse has a .tables attribute (lancedb 0.27+)
        if hasattr(raw, "tables"):
            return list(raw.tables or [])
        # Form 2: already a plain list
        if isinstance(raw, list):
            return raw
        # Form 3: coerce iterable to list
        try:
            return list(raw)
        except TypeError:
            return []

    def drop_table(self, name: str) -> None:
        self.connect().drop_table(name)

    def upsert(self, table_name: str, records: list[dict[str, Any]]) -> None:
        """Add records to a table (append mode — vector dedup handled by callers)."""
        self.connect().open_table(table_name).add(records)

    def search(
        self,
        table_name: str,
        query_vector: list[float],
        limit: int = 5,
        where: str | None = None,
    ) -> list[dict[str, Any]]:
        """ANN search. Returns list of dicts ordered by distance."""
        tbl = self.connect().open_table(table_name)
        q = tbl.search(query_vector).limit(limit)
        if where:
            q = q.where(where)
        return q.to_list()

    @property
    def uri(self) -> str:
        return self._uri


# ─── Module-level singleton ───────────────────────────────────────────────────
lancedb_client = LanceDBClient()
