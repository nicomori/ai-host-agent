"""
Shared pytest fixtures for ai-host-agent.
Each step has dedicated fixtures so it can be tested in isolation.

Step isolation pattern:
  - Each step fixture sets LANCEDB_URI to a tmpdir
  - Clears get_settings lru_cache before and after
  - Resets graph singleton where applicable
  - Uses MemorySaver for LangGraph tests (no disk I/O)
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Docker infra: no runtime deps, fixture is a simple marker
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step1_project_root():
    """Return the project root path for infra file checks."""
    import pathlib

    return pathlib.Path(__file__).parent.parent


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — LanceDB client
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step2_lancedb_tmp() -> Generator[str, None, None]:
    """Temporary LanceDB directory — isolated per test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


@pytest.fixture()
def step2_lancedb_client(step2_lancedb_tmp):
    """LanceDBClient connected to an isolated tmpdir."""
    from src.services.lancedb_client import LanceDBClient

    client = LanceDBClient(uri=step2_lancedb_tmp)
    client.init_tables()
    return client


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Config
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step3_settings(step2_lancedb_tmp):
    """AppSettings with LANCEDB_URI pointed at tmpdir, cache cleared."""
    os.environ["LANCEDB_URI"] = step2_lancedb_tmp
    from src.config import get_settings

    get_settings.cache_clear()
    cfg = get_settings()
    yield cfg
    get_settings.cache_clear()
    os.environ.pop("LANCEDB_URI", None)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — FastAPI app + TestClient
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step4_client(step2_lancedb_tmp) -> Generator[TestClient, None, None]:
    """
    TestClient pointing at a fresh app instance with isolated LanceDB.
    Graph singleton reset before each test to avoid cross-contamination.
    """
    os.environ["LANCEDB_URI"] = step2_lancedb_tmp
    from src.config import get_settings

    get_settings.cache_clear()
    from src.agents.graph import reset_graph

    reset_graph()
    from src.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    get_settings.cache_clear()
    os.environ.pop("LANCEDB_URI", None)
    reset_graph()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — LangGraph agent (MemorySaver — fast, no disk I/O)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step5_memory_checkpointer():
    """Fresh MemorySaver for agent graph tests."""
    return MemorySaver()


@pytest.fixture()
def step5_graph(step5_memory_checkpointer):
    """Compiled LangGraph graph with MemorySaver, reset after test."""
    from src.agents.graph import build_graph, reset_graph

    reset_graph()
    graph = build_graph(checkpointer=step5_memory_checkpointer)
    yield graph
    reset_graph()


@pytest.fixture()
def step5_session_id():
    """Unique session ID per test."""
    return str(uuid.uuid4())


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Persistent checkpointing (SqliteSaver)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step6_sqlite_path(tmp_path):
    """Temporary SQLite path for SqliteSaver tests."""
    return str(tmp_path / "checkpoints.sqlite")


@pytest.fixture()
def step6_sqlite_checkpointer(step6_sqlite_path):
    """SqliteSaver connected to a temp file."""
    from src.checkpointing import get_checkpointer

    return get_checkpointer(use_sqlite=True, db_path=step6_sqlite_path)


@pytest.fixture()
def step6_graph(step6_sqlite_checkpointer):
    """Graph compiled with SqliteSaver for persistence tests."""
    from src.agents.graph import build_graph, reset_graph

    reset_graph()
    graph = build_graph(checkpointer=step6_sqlite_checkpointer)
    yield graph
    reset_graph()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Context window management
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def step7_context_budget():
    """A tight ContextBudget for testing trimming logic."""
    from src.context_window import ContextBudget

    return ContextBudget(
        agent_name="TestAgent", token_limit=50, alert_threshold=0.80, strategy="sliding"
    )


@pytest.fixture()
def step7_large_history():
    """20-message conversation history that exceeds any small budget."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    msgs = [SystemMessage(content="You are HostAI, a restaurant assistant.")]
    for i in range(10):
        msgs.append(
            HumanMessage(content=f"I want to book a table for {i + 1} people at 7pm on Saturday")
        )
        msgs.append(
            AIMessage(
                content=f"Sure! I can book a table for {i + 1} people. Please confirm your name."
            )
        )
    return msgs
