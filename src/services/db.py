"""
PostgreSQL persistence layer — ai-host-agent (Step 3+)

Tables managed here:
  reservations  — guest reservations (Step 7)
  call_logs     — inbound/outbound voice calls (Step 9)
  agent_sessions — conversation session state (Step 10)

Uses psycopg2 (sync) for simplicity; can be swapped to asyncpg for async routes.
Connection credentials are read from AppSettings (env vars / .env).
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
import psycopg2.extras

from src.config import get_settings

logger = logging.getLogger(__name__)

# ─── DDL — create tables if they don't exist ──────────────────────────────────

_DDL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS reservations (
    id              SERIAL PRIMARY KEY,
    reservation_id  UUID NOT NULL DEFAULT gen_random_uuid(),
    guest_name      TEXT NOT NULL,
    guest_phone     TEXT NOT NULL,
    date            DATE NOT NULL,
    time            TIME NOT NULL,
    party_size      INTEGER NOT NULL DEFAULT 2,
    status          TEXT NOT NULL DEFAULT 'confirmed',
    preference      TEXT,
    special_requests TEXT,
    notes           TEXT,
    confirmation_status  TEXT NOT NULL DEFAULT 'pending',
    confirmation_called_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS reservations_reservation_id_key ON reservations(reservation_id);

CREATE TABLE IF NOT EXISTS call_logs (
    id              SERIAL PRIMARY KEY,
    call_sid        TEXT UNIQUE NOT NULL,
    from_number     TEXT NOT NULL,
    to_number       TEXT NOT NULL,
    call_status     TEXT NOT NULL,
    duration_sec    INTEGER,
    transcript      TEXT,
    intent          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT UNIQUE NOT NULL,
    call_sid        TEXT,
    messages        JSONB NOT NULL DEFAULT '[]',
    intent          TEXT,
    reservation_data JSONB,
    agent_trace     JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


# ─── Connection factory ────────────────────────────────────────────────────────


def _get_dsn() -> str:
    s = get_settings()
    return (
        f"host={s.env.postgres_host} "
        f"port={s.env.postgres_port} "
        f"dbname={s.env.postgres_db} "
        f"user={s.env.postgres_user} "
        f"password={s.env.postgres_password}"
    )


_db_initialized = False


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager yielding a psycopg2 connection with autocommit disabled."""
    conn = psycopg2.connect(_get_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        _auto_reinit_db()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─── Schema init ───────────────────────────────────────────────────────────────


def init_db() -> None:
    """Create tables if they don't exist. Called at app startup."""
    global _db_initialized
    try:
        with psycopg2.connect(_get_dsn(), cursor_factory=psycopg2.extras.RealDictCursor) as conn:
            with conn.cursor() as cur:
                cur.execute(_DDL)
                cur.execute(
                    "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS confirmation_status TEXT NOT NULL DEFAULT 'pending';"
                )
                cur.execute(
                    "ALTER TABLE reservations ADD COLUMN IF NOT EXISTS confirmation_called_at TIMESTAMPTZ;"
                )
            conn.commit()
        _db_initialized = True
        logger.info("[HostAI] - DB Init: PostgreSQL schema initialized (host-agent)")
    except Exception as exc:
        logger.warning("[HostAI] - DB Init: PostgreSQL init_db failed (non-fatal): %s", exc)


def _auto_reinit_db() -> None:
    """Re-initialize DB schema when an UndefinedTable error is detected (e.g. after Postgres restart without PVC)."""
    global _db_initialized
    if not _db_initialized:
        return
    logger.warning("[HostAI] - DB: UndefinedTable detected — re-initializing all schemas")
    _db_initialized = False
    init_db()
    try:
        from src.api.auth_users import ensure_default_users
        from src.services.floor_plan_service import ensure_assignments_table
        ensure_default_users()
        ensure_assignments_table()
    except Exception as exc:
        logger.warning("[HostAI] - DB: reinit auxiliary tables failed: %s", exc)


# ─── Reservations ─────────────────────────────────────────────────────────────


def _row_to_reservation(row: dict) -> dict:
    """Convert a DB row to the API dict shape. Includes both 'id' (SERIAL) and 'reservation_id' (UUID)."""
    called_at = row.get("confirmation_called_at")
    return {
        "id": row.get("id"),  # SERIAL PK — kept for legacy tests
        "reservation_id": str(row["reservation_id"]),
        "guest_name": row["guest_name"],
        "guest_phone": row["guest_phone"],
        "date": str(row["date"]),
        "time": str(row["time"])[:5],  # HH:MM
        "party_size": row["party_size"],
        "status": row["status"],
        "preference": row.get("preference"),
        "special_requests": row.get("special_requests"),
        "notes": row.get("notes"),
        "confirmation_status": row.get("confirmation_status", "pending"),
        "confirmation_called_at": str(called_at) if called_at else None,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def save_reservation(
    guest_name: str,
    guest_phone: str,
    date: str,
    time: str,
    party_size: int = 2,
    reservation_id: str | None = None,
    preference: str | None = None,
    special_requests: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Insert a reservation row and return the created record."""
    import uuid as _uuid

    rid = reservation_id or str(_uuid.uuid4())
    sql = """
        INSERT INTO reservations
            (reservation_id, guest_name, guest_phone, date, time, party_size,
             preference, special_requests, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    rid,
                    guest_name,
                    guest_phone,
                    date,
                    time,
                    party_size,
                    preference,
                    special_requests,
                    notes,
                ),
            )
            row = cur.fetchone()
    return _row_to_reservation(dict(row))


def get_reservation_by_uuid(reservation_id: str) -> dict[str, Any] | None:
    import uuid as _uuid

    try:
        _uuid.UUID(reservation_id)  # validate format before querying
    except (ValueError, AttributeError):
        return None  # invalid UUID → not found
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM reservations WHERE reservation_id = %s",
                (reservation_id,),
            )
            row = cur.fetchone()
    return _row_to_reservation(dict(row)) if row else None


def get_reservation(reservation_id: int | str) -> dict[str, Any] | None:
    """Lookup by SERIAL int id or UUID string."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if isinstance(reservation_id, int):
                cur.execute("SELECT * FROM reservations WHERE id = %s", (reservation_id,))
            else:
                cur.execute(
                    "SELECT * FROM reservations WHERE reservation_id = %s", (reservation_id,)
                )
            row = cur.fetchone()
    return _row_to_reservation(dict(row)) if row else None


def list_reservations(
    status_filter: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status_filter:
                cur.execute(
                    "SELECT * FROM reservations WHERE status=%s ORDER BY date, time, created_at DESC LIMIT %s",
                    (status_filter, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM reservations ORDER BY date, time, created_at DESC LIMIT %s",
                    (limit,),
                )
            return [_row_to_reservation(dict(r)) for r in cur.fetchall()]


def update_reservation_status(
    reservation_id: str | int,
    new_status: str,
    notes: str | None = None,
) -> bool:
    """Update status by UUID string (routes) or SERIAL int (legacy tests)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if isinstance(reservation_id, int):
                # Legacy path: SERIAL id
                cur.execute(
                    "UPDATE reservations SET status=%s, notes=COALESCE(%s, notes), updated_at=NOW() WHERE id=%s",
                    (new_status, notes, reservation_id),
                )
            else:
                # New path: UUID string
                cur.execute(
                    "UPDATE reservations SET status=%s, notes=COALESCE(%s, notes), updated_at=NOW() WHERE reservation_id=%s",
                    (new_status, notes, reservation_id),
                )
            return cur.rowcount > 0


def update_confirmation_status(
    reservation_id: str,
    confirmation_status: str,
) -> bool:
    """Update the confirmation call status for a reservation."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE reservations SET confirmation_status=%s, confirmation_called_at=NOW(), updated_at=NOW() WHERE reservation_id=%s",
                (confirmation_status, reservation_id),
            )
            return cur.rowcount > 0


def truncate_reservations() -> None:
    """Delete all reservations — used in test teardown."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reservations")


# ─── Call logs ────────────────────────────────────────────────────────────────


def save_call_log(
    call_sid: str,
    from_number: str,
    to_number: str,
    call_status: str,
    duration_sec: int | None = None,
    transcript: str | None = None,
    intent: str | None = None,
) -> dict[str, Any]:
    sql = """
        INSERT INTO call_logs
            (call_sid, from_number, to_number, call_status, duration_sec, transcript, intent)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (call_sid) DO UPDATE
            SET call_status=EXCLUDED.call_status,
                duration_sec=EXCLUDED.duration_sec,
                transcript=EXCLUDED.transcript,
                intent=EXCLUDED.intent
        RETURNING *
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (call_sid, from_number, to_number, call_status, duration_sec, transcript, intent),
            )
            row = cur.fetchone()
    return dict(row)


def get_call_log(call_sid: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM call_logs WHERE call_sid = %s", (call_sid,))
            row = cur.fetchone()
    return dict(row) if row else None


# ─── Agent sessions ───────────────────────────────────────────────────────────


def save_agent_session(
    session_id: str,
    call_sid: str | None,
    messages: list[dict],
    intent: str | None = None,
    reservation_data: dict | None = None,
    agent_trace: list | None = None,
) -> dict[str, Any]:
    sql = """
        INSERT INTO agent_sessions
            (session_id, call_sid, messages, intent, reservation_data, agent_trace)
        VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb)
        ON CONFLICT (session_id) DO UPDATE
            SET messages=EXCLUDED.messages,
                intent=EXCLUDED.intent,
                reservation_data=EXCLUDED.reservation_data,
                agent_trace=EXCLUDED.agent_trace,
                updated_at=NOW()
        RETURNING *
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    session_id,
                    call_sid,
                    json.dumps(messages),
                    intent,
                    json.dumps(reservation_data) if reservation_data else None,
                    json.dumps(agent_trace) if agent_trace else None,
                ),
            )
            row = cur.fetchone()
    return dict(row)


def get_agent_session(session_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_sessions WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
    return dict(row) if row else None
