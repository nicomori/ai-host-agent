"""
DB Persistence Tests — ai-host-agent

15 test cases covering PostgreSQL persistence via src/services/db.py:
  TC-01: init_db() runs without error
  TC-02: save_reservation() returns a dict with 'id'
  TC-03: get_reservation() returns the saved record
  TC-04: list_reservations() returns a non-empty list after save
  TC-05: update_reservation_status() changes status to 'cancelled'
  TC-06: save_call_log() returns a dict with 'id'
  TC-07: get_call_log() retrieves by call_sid
  TC-08: save_call_log() is idempotent (ON CONFLICT DO UPDATE)
  TC-09: save_agent_session() returns dict with 'id'
  TC-10: get_agent_session() retrieves by session_id
  TC-11: save_agent_session() is idempotent (ON CONFLICT DO UPDATE)
  TC-12: list_reservations() obeys limit parameter
  TC-13: save_reservation() stores party_size correctly
  TC-14: save_call_log() stores transcript and intent
  TC-15: save_agent_session() stores messages as list

Error resolutions applied:
  Form 1: psycopg2 connection via env vars (localhost:5433)
  Form 2: ON CONFLICT DO UPDATE for idempotency
  Form 3: RealDictCursor for dict-style row access
  Form 4: Non-fatal try/except in route layer
  Form 5: contextmanager for automatic conn.close()
"""

from __future__ import annotations

import os
import uuid

import pytest

# ─── Skip entire module if psycopg2 not available or DB unreachable ───────────

psycopg2 = pytest.importorskip("psycopg2")

# Set env vars for test DB connection before importing db module
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("POSTGRES_DB", "hostai_db")
os.environ.setdefault("POSTGRES_USER", "hostai_user")
os.environ.setdefault("POSTGRES_PASSWORD", "hostai_pass_2026")
os.environ.setdefault("LANCEDB_URI", "/tmp/hostai_lancedb_test")

from src.config import get_settings  # noqa: E402

get_settings.cache_clear()

from src.services import db as pg_db  # noqa: E402


def _reachable() -> bool:
    try:
        with pg_db.get_conn():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason="PostgreSQL not reachable at localhost:5433",
)

_CALL_SID = f"CA-test-{uuid.uuid4().hex[:8]}"
_SESSION_ID = f"sess-{uuid.uuid4().hex[:8]}"


# ─── TC-01 ────────────────────────────────────────────────────────────────────


def test_tc01_init_db_runs_without_error():
    """TC-01: init_db() must complete without raising."""
    pg_db.init_db()  # idempotent


# ─── TC-02 ────────────────────────────────────────────────────────────────────


def test_tc02_save_reservation_returns_dict_with_id():
    """TC-02: save_reservation() must return a dict containing 'id'."""
    row = pg_db.save_reservation(
        guest_name="Test Guest",
        guest_phone="+54911555000",
        date="2026-07-01",
        time="20:00",
        party_size=4,
    )
    print(f"\nTC-02 row: {row}")
    assert isinstance(row, dict)
    assert "id" in row
    assert row["guest_name"] == "Test Guest"


# ─── TC-03 ────────────────────────────────────────────────────────────────────


def test_tc03_get_reservation_returns_saved_record():
    """TC-03: get_reservation(id) must return the saved record."""
    saved = pg_db.save_reservation(
        guest_name="Get Test",
        guest_phone="+54911555001",
        date="2026-07-02",
        time="19:00",
        party_size=2,
    )
    retrieved = pg_db.get_reservation(saved["id"])
    print(f"\nTC-03 retrieved: {retrieved}")
    assert retrieved is not None
    assert retrieved["id"] == saved["id"]
    assert retrieved["guest_name"] == "Get Test"


# ─── TC-04 ────────────────────────────────────────────────────────────────────


def test_tc04_list_reservations_non_empty_after_save():
    """TC-04: list_reservations() must return ≥ 1 record after TC-02."""
    pg_db.save_reservation("List Test", "+54911555002", "2026-07-03", "18:00", 3)
    rows = pg_db.list_reservations()
    print(f"\nTC-04 count: {len(rows)}")
    assert len(rows) >= 1


# ─── TC-05 ────────────────────────────────────────────────────────────────────


def test_tc05_update_reservation_status_to_cancelled():
    """TC-05: update_reservation_status() must set status to 'cancelled'."""
    saved = pg_db.save_reservation(
        guest_name="Cancel Test",
        guest_phone="+54911555003",
        date="2026-07-04",
        time="21:00",
        party_size=2,
    )
    result = pg_db.update_reservation_status(saved["id"], "cancelled")
    retrieved = pg_db.get_reservation(saved["id"])
    print(f"\nTC-05 update result: {result}, status: {retrieved['status']}")
    assert result is True
    assert retrieved["status"] == "cancelled"


# ─── TC-06 ────────────────────────────────────────────────────────────────────


def test_tc06_save_call_log_returns_dict_with_id():
    """TC-06: save_call_log() must return a dict with 'id'."""
    row = pg_db.save_call_log(
        call_sid=_CALL_SID,
        from_number="+54911999000",
        to_number="+54911000001",
        call_status="ringing",
    )
    print(f"\nTC-06 call_log row: {row}")
    assert isinstance(row, dict)
    assert "id" in row
    assert row["call_sid"] == _CALL_SID


# ─── TC-07 ────────────────────────────────────────────────────────────────────


def test_tc07_get_call_log_retrieves_by_sid():
    """TC-07: get_call_log(call_sid) must return the record saved in TC-06."""
    retrieved = pg_db.get_call_log(_CALL_SID)
    print(f"\nTC-07 call_log: {retrieved}")
    assert retrieved is not None
    assert retrieved["call_sid"] == _CALL_SID


# ─── TC-08 ────────────────────────────────────────────────────────────────────


def test_tc08_save_call_log_is_idempotent():
    """TC-08: Saving the same call_sid twice must not raise (ON CONFLICT DO UPDATE)."""
    pg_db.save_call_log(_CALL_SID, "+54911999000", "+54911000001", "ringing")
    row2 = pg_db.save_call_log(_CALL_SID, "+54911999000", "+54911000001", "in-progress")
    print(f"\nTC-08 second save status: {row2['call_status']}")
    assert row2["call_status"] == "in-progress"


# ─── TC-09 ────────────────────────────────────────────────────────────────────


def test_tc09_save_agent_session_returns_dict():
    """TC-09: save_agent_session() must return a dict with 'id'."""
    row = pg_db.save_agent_session(
        session_id=_SESSION_ID,
        call_sid=_CALL_SID,
        messages=[{"role": "user", "content": "I need a reservation"}],
        intent="make_reservation",
    )
    print(f"\nTC-09 session row: {row}")
    assert isinstance(row, dict)
    assert "id" in row
    assert row["session_id"] == _SESSION_ID


# ─── TC-10 ────────────────────────────────────────────────────────────────────


def test_tc10_get_agent_session_retrieves_by_id():
    """TC-10: get_agent_session() must return the saved session."""
    retrieved = pg_db.get_agent_session(_SESSION_ID)
    print(f"\nTC-10 session: {retrieved}")
    assert retrieved is not None
    assert retrieved["intent"] == "make_reservation"


# ─── TC-11 ────────────────────────────────────────────────────────────────────


def test_tc11_save_agent_session_is_idempotent():
    """TC-11: save_agent_session() with same session_id must update (ON CONFLICT DO UPDATE)."""
    row = pg_db.save_agent_session(
        session_id=_SESSION_ID,
        call_sid=_CALL_SID,
        messages=[{"role": "assistant", "content": "Reservation made!"}],
        intent="reservation_confirmed",
    )
    print(f"\nTC-11 updated intent: {row['intent']}")
    assert row["intent"] == "reservation_confirmed"


# ─── TC-12 ────────────────────────────────────────────────────────────────────


def test_tc12_list_reservations_obeys_limit():
    """TC-12: list_reservations(limit=1) must return at most 1 record."""
    rows = pg_db.list_reservations(limit=1)
    print(f"\nTC-12 limit=1 count: {len(rows)}")
    assert len(rows) <= 1


# ─── TC-13 ────────────────────────────────────────────────────────────────────


def test_tc13_save_reservation_stores_party_size():
    """TC-13: party_size must be stored and retrievable."""
    saved = pg_db.save_reservation(
        guest_name="Party Size Test",
        guest_phone="+54911555010",
        date="2026-08-01",
        time="20:30",
        party_size=8,
    )
    retrieved = pg_db.get_reservation(saved["id"])
    print(f"\nTC-13 party_size: {retrieved['party_size']}")
    assert retrieved["party_size"] == 8


# ─── TC-14 ────────────────────────────────────────────────────────────────────


def test_tc14_save_call_log_stores_transcript_and_intent():
    """TC-14: save_call_log with transcript and intent must persist both fields."""
    sid = f"CA-tc14-{uuid.uuid4().hex[:6]}"
    pg_db.save_call_log(
        call_sid=sid,
        from_number="+54911100014",
        to_number="+54911000001",
        call_status="completed",
        transcript="I need a table for 2",
        intent="make_reservation",
    )
    retrieved = pg_db.get_call_log(sid)
    print(f"\nTC-14 transcript={retrieved['transcript']} intent={retrieved['intent']}")
    assert retrieved["transcript"] == "I need a table for 2"
    assert retrieved["intent"] == "make_reservation"


# ─── TC-15 ────────────────────────────────────────────────────────────────────


def test_tc15_save_agent_session_stores_messages_as_list():
    """TC-15: messages stored in agent_sessions must be retrievable as a list."""
    sid = f"sess-tc15-{uuid.uuid4().hex[:6]}"
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
    ]
    pg_db.save_agent_session(session_id=sid, call_sid=None, messages=messages)
    retrieved = pg_db.get_agent_session(sid)
    print(f"\nTC-15 messages type: {type(retrieved['messages'])}")
    # JSONB column returns dict/list depending on psycopg2 version
    stored_messages = retrieved["messages"]
    if isinstance(stored_messages, str):
        import json

        stored_messages = json.loads(stored_messages)
    assert isinstance(stored_messages, list)
    assert len(stored_messages) == 2
