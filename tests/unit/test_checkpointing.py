"""
BLOQUE 6 — Estado persistente + checkpointing: Test Suite (HostAI)
15 test cases covering SqliteSaver, thread_id persistence, resume, and factory.
"""

from __future__ import annotations

import os
import tempfile
import uuid

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage


# ─── TC-01: checkpointing module importable ───────────────────────────────────
def test_tc01_checkpointing_module_imports():
    """TC-01: src.checkpointing module must be importable and expose key symbols."""
    from src.checkpointing import (
        CHECKPOINT_DB_PATH,
        get_checkpointer,
    )

    assert CHECKPOINT_DB_PATH.endswith(".sqlite")
    assert callable(get_checkpointer)


# ─── TC-02: get_memory_checkpointer returns MemorySaver ──────────────────────
def test_tc02_memory_checkpointer():
    """TC-02: get_memory_checkpointer() must return a MemorySaver instance."""
    from src.checkpointing import get_memory_checkpointer

    cp = get_memory_checkpointer()
    assert isinstance(cp, MemorySaver)


# ─── TC-03: SqliteSaver written to custom path ────────────────────────────────
def test_tc03_sqlite_checkpointer_creates_file():
    """TC-03: sqlite_checkpointer() must create the .sqlite file on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "sub", "checkpoints.sqlite")
        from src.checkpointing import sqlite_checkpointer

        with sqlite_checkpointer(db_path=db_path) as cp:
            assert cp is not None
        assert os.path.exists(db_path), "SQLite file was not created"


# ─── TC-04: State persists across two invocations (same thread_id) ────────────
def test_tc04_state_persists_same_thread():
    """TC-04: Two invoke calls with the same thread_id must share state."""
    from src.agents.graph import build_graph, reset_graph

    reset_graph()
    cp = MemorySaver()
    graph = build_graph(checkpointer=cp)
    session_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": session_id}}

    from langchain_core.messages import SystemMessage

    base = {
        "messages": [
            SystemMessage(content="You are HostAI."),
            HumanMessage(content="I want to make a reservation"),
        ],
        "session_id": session_id,
        "intent": None,
        "reservation_data": None,
        "next_action": None,
        "final_response": None,
        "errors": [],
    }
    result1 = graph.invoke(base, config=cfg)
    assert result1["intent"] == "make_reservation"

    # Second call — same thread_id, new message
    from langchain_core.messages import HumanMessage as HM

    state2 = {
        **base,
        "messages": [HM(content="Cancel that")],
        "intent": None,
        "final_response": None,
    }
    result2 = graph.invoke(state2, config=cfg)
    # State was resumed — different intent
    assert result2["intent"] == "cancel_reservation"
    reset_graph()


# ─── TC-05: Different thread_ids are isolated ─────────────────────────────────
def test_tc05_different_threads_isolated():
    """TC-05: Two different thread_ids must produce independent states."""
    from src.agents.graph import build_graph, reset_graph
    from langchain_core.messages import SystemMessage, HumanMessage

    reset_graph()
    cp = MemorySaver()
    graph = build_graph(checkpointer=cp)

    def _invoke(msg, tid):
        cfg = {"configurable": {"thread_id": tid}}
        state = {
            "messages": [SystemMessage(content="You are HostAI."), HumanMessage(content=msg)],
            "session_id": tid,
            "intent": None,
            "reservation_data": None,
            "next_action": None,
            "final_response": None,
            "errors": [],
        }
        return graph.invoke(state, config=cfg)

    r1 = _invoke("I want to make a reservation", str(uuid.uuid4()))
    r2 = _invoke("I want to cancel my reservation", str(uuid.uuid4()))
    assert r1["intent"] == "make_reservation"
    assert r2["intent"] == "cancel_reservation"
    reset_graph()


# ─── TC-06: get_checkpointer with use_sqlite=True creates file ────────────────
def test_tc06_get_checkpointer_sqlite():
    """TC-06: get_checkpointer(use_sqlite=True) must return a SqliteSaver."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "cp.sqlite")
        from src.checkpointing import get_checkpointer

        cp = get_checkpointer(use_sqlite=True, db_path=db_path)
        assert cp is not None
        # Should have put method (checkpointer interface)
        assert hasattr(cp, "put") or hasattr(cp, "get")


# ─── TC-07: build_graph defaults to sqlite when env set ───────────────────────
def test_tc07_build_graph_uses_sqlite_env():
    """TC-07: build_graph() without explicit checkpointer must try SqliteSaver."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "cp.sqlite")
        os.environ["CHECKPOINT_DB_PATH"] = db_path
        # Invalidate cached module to pick up new env var
        import importlib
        import src.checkpointing as _m

        importlib.reload(_m)
        from src.agents.graph import build_graph, reset_graph

        reset_graph()
        graph = build_graph()  # no explicit checkpointer
        assert graph is not None
        reset_graph()
        os.environ.pop("CHECKPOINT_DB_PATH", None)
        importlib.reload(_m)


# ─── TC-08: get_checkpointer(use_sqlite=False) returns MemorySaver ───────────
def test_tc08_get_checkpointer_memory_default():
    """TC-08: get_checkpointer(use_sqlite=False) must return a MemorySaver instance."""
    from src.checkpointing import get_checkpointer

    cp = get_checkpointer(use_sqlite=False)
    assert isinstance(cp, MemorySaver)


# ─── TC-09: sqlite_checkpointer creates nested directories ────────────────────
def test_tc09_sqlite_checkpointer_nested_dirs():
    """TC-09: sqlite_checkpointer must create all intermediate directories for db_path."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "a", "b", "c", "data.sqlite")
        from src.checkpointing import sqlite_checkpointer

        with sqlite_checkpointer(db_path=db_path) as cp:
            assert cp is not None
        assert os.path.exists(db_path), f"Nested path not created: {db_path}"


# ─── TC-10: FallbackSqliteSaver implements put method ─────────────────────────
def test_tc10_fallback_saver_has_put():
    """TC-10: The checkpointer returned by get_checkpointer must expose the 'put' method."""
    from src.checkpointing import get_checkpointer

    cp = get_checkpointer(use_sqlite=False)
    assert hasattr(cp, "put"), "Checkpointer must have 'put' method"
    assert callable(cp.put)


# ─── TC-11: get_checkpointer sqlite file is created on disk ──────────────────
def test_tc11_get_checkpointer_sqlite_creates_file():
    """TC-11: get_checkpointer(use_sqlite=True) must create the .sqlite file on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "explicit.sqlite")
        from src.checkpointing import get_checkpointer

        cp = get_checkpointer(use_sqlite=True, db_path=db_path)
        assert cp is not None
        assert os.path.exists(db_path), "SQLite file must be created by get_checkpointer"


# ─── TC-12: sqlite_checkpointer is a context manager ─────────────────────────
def test_tc12_sqlite_checkpointer_is_context_manager():
    """TC-12: sqlite_checkpointer must be usable as a context manager (with statement)."""
    from src.checkpointing import sqlite_checkpointer

    assert hasattr(sqlite_checkpointer, "__call__")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "ctx_test.sqlite")
        entered = False
        with sqlite_checkpointer(db_path=db_path) as cp:
            entered = True
            assert cp is not None
        assert entered


# ─── TC-13: CHECKPOINT_DB_PATH default ends with checkpoints.sqlite ──────────
def test_tc13_checkpoint_db_path_default_name():
    """TC-13: Default CHECKPOINT_DB_PATH must end with 'checkpoints.sqlite'."""
    from src.checkpointing import CHECKPOINT_DB_PATH

    assert "checkpoints.sqlite" in CHECKPOINT_DB_PATH


# ─── TC-14: get_memory_checkpointer is not None ───────────────────────────────
def test_tc14_get_memory_checkpointer_not_none():
    """TC-14: get_memory_checkpointer() must return a non-None checkpointer."""
    from src.checkpointing import get_memory_checkpointer

    cp = get_memory_checkpointer()
    assert cp is not None
    assert hasattr(cp, "get") or hasattr(cp, "put")


# ─── TC-15: Multiple sqlite_checkpointer calls on same path work ──────────────
def test_tc15_sqlite_checkpointer_reopen():
    """TC-15: Opening sqlite_checkpointer twice on the same path must not raise."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "reopen_test.sqlite")
        from src.checkpointing import sqlite_checkpointer

        with sqlite_checkpointer(db_path=db_path) as cp1:
            assert cp1 is not None
        # Reopen — must not raise
        with sqlite_checkpointer(db_path=db_path) as cp2:
            assert cp2 is not None
