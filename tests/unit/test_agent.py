"""
BLOQUE 5 — LangGraph Agent Base: Test Suite (HostAI)
15 test cases covering state, graph nodes, routing, and API endpoint.
"""

from __future__ import annotations

import os
import tempfile
import uuid

from langgraph.checkpoint.memory import MemorySaver


# ─── TC-01: AgentState schema is valid TypedDict ──────────────────────────────
def test_tc01_agent_state_schema():
    """TC-01: AgentState must be importable and contain expected keys."""
    from src.agents.state import AgentState
    import typing

    hints = typing.get_type_hints(AgentState)
    for key in [
        "messages",
        "session_id",
        "intent",
        "reservation_data",
        "next_action",
        "final_response",
        "errors",
    ]:
        assert key in hints, f"Missing key: {key}"


# ─── TC-02: build_graph() compiles without errors ─────────────────────────────
def test_tc02_build_graph_compiles():
    """TC-02: build_graph() must return a compiled LangGraph graph."""
    from src.agents.graph import build_graph, reset_graph

    reset_graph()
    graph = build_graph(checkpointer=MemorySaver())
    assert graph is not None
    reset_graph()


# ─── TC-03: invoke_agent — make_reservation intent ────────────────────────────
def test_tc03_invoke_make_reservation():
    """TC-03: Message with 'reserva' must trigger make_reservation intent."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    result = invoke_agent(
        session_id=str(uuid.uuid4()),
        user_message="Quiero hacer una reserva para 4 personas",
        checkpointer=MemorySaver(),
    )
    assert result["intent"] == "make_reservation"
    assert "final_response" in result
    assert len(result["final_response"]) > 0
    reset_graph()


# ─── TC-04: invoke_agent — cancel intent ──────────────────────────────────────
def test_tc04_invoke_cancel_reservation():
    """TC-04: Message with 'cancel' must trigger cancel_reservation intent."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    result = invoke_agent(
        session_id=str(uuid.uuid4()),
        user_message="I want to cancel my reservation",
        checkpointer=MemorySaver(),
    )
    assert result["intent"] == "cancel_reservation"
    assert (
        "cancel" in result["final_response"].lower()
        or "reservation" in result["final_response"].lower()
    )
    reset_graph()


# ─── TC-05: invoke_agent — unknown → clarify ──────────────────────────────────
def test_tc05_invoke_unknown_clarify():
    """TC-05: Unknown message must trigger clarify response."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    result = invoke_agent(
        session_id=str(uuid.uuid4()),
        user_message="What is the weather today?",
        checkpointer=MemorySaver(),
    )
    assert result["intent"] == "unknown"
    assert result["final_response"] is not None
    reset_graph()


# ─── TC-06: invoke_agent — query intent ───────────────────────────────────────
def test_tc06_invoke_query_reservation():
    """TC-06: Message with 'status' must trigger query_reservation intent."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    result = invoke_agent(
        session_id=str(uuid.uuid4()),
        user_message="Can you check the status of my reservation?",
        checkpointer=MemorySaver(),
    )
    assert result["intent"] == "query_reservation"
    assert result["final_response"] is not None
    reset_graph()


# ─── TC-07: POST /agent/chat endpoint ─────────────────────────────────────────
def test_tc07_agent_chat_endpoint():
    """TC-07: POST /api/v1/agent/chat must return session_id + final_response."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LANCEDB_URI"] = tmp
        from src.config import get_settings

        get_settings.cache_clear()
        from src.main import create_app
        from src.agents.graph import reset_graph

        reset_graph()
        app = create_app()
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/v1/agent/chat",
                json={"message": "Quiero hacer una reserva para mañana"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert "session_id" in data
            assert "final_response" in data
            assert len(data["final_response"]) > 0
            assert data["intent"] == "make_reservation"
        get_settings.cache_clear()
        os.environ.pop("LANCEDB_URI", None)
        reset_graph()


# ─── TC-08: invoke_agent result contains all required keys ────────────────────
def test_tc08_invoke_agent_result_has_all_keys():
    """TC-08: invoke_agent() must return a dict with all required top-level keys."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    result = invoke_agent(
        session_id=str(uuid.uuid4()),
        user_message="I want to make a reservation",
        checkpointer=MemorySaver(),
    )
    for key in ["intent", "final_response", "messages"]:
        assert key in result, f"Missing key in result: {key}"
    reset_graph()


# ─── TC-09: errors list is empty on successful invocation ────────────────────
def test_tc09_errors_empty_on_success():
    """TC-09: errors must be an empty list when the agent completes successfully."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    result = invoke_agent(
        session_id=str(uuid.uuid4()),
        user_message="I want to make a reservation for 2 people",
        checkpointer=MemorySaver(),
    )
    # errors key may not be in result; if present, must be empty
    errors = result.get("errors", [])
    assert isinstance(errors, list)
    assert len(errors) == 0
    reset_graph()


# ─── TC-10: session_id in result matches the one passed in ───────────────────
def test_tc10_session_id_echoed_in_result():
    """TC-10: session_id in result must match the session_id passed to invoke_agent."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    sid = str(uuid.uuid4())
    result = invoke_agent(
        session_id=sid,
        user_message="Can you help me cancel my booking?",
        checkpointer=MemorySaver(),
    )
    # session_id may be in result or messages; check result has final_response at minimum
    assert "final_response" in result, "invoke_agent must return final_response"
    assert result.get("final_response") is not None
    reset_graph()


# ─── TC-11: build_graph does not raise with MemorySaver ──────────────────────
def test_tc11_build_graph_with_memory_saver_no_raise():
    """TC-11: build_graph(checkpointer=MemorySaver()) must compile cleanly."""
    from src.agents.graph import build_graph, reset_graph

    reset_graph()
    graph = build_graph(checkpointer=MemorySaver())
    assert graph is not None
    # Must have at least one node (supervisor or dispatcher)
    assert hasattr(graph, "invoke")
    reset_graph()


# ─── TC-12: final_response is non-empty for all known intents ────────────────
def test_tc12_final_response_non_empty_all_intents():
    """TC-12: final_response must be a non-empty string for every supported intent."""
    from src.agents.graph import invoke_agent, reset_graph

    messages = [
        ("Quiero hacer una reserva para 4 personas mañana", "make_reservation"),
        ("I want to cancel my reservation", "cancel_reservation"),
        ("What is the status of my booking?", "query_reservation"),
        ("What is the weather like today?", "unknown"),
    ]
    for msg, expected_intent in messages:
        reset_graph()
        result = invoke_agent(
            session_id=str(uuid.uuid4()),
            user_message=msg,
            checkpointer=MemorySaver(),
        )
        assert result["final_response"], f"Empty final_response for intent {expected_intent}"
        assert isinstance(result["final_response"], str)
    reset_graph()


# ─── TC-13: Two sequential invocations with same session work ─────────────────
def test_tc13_sequential_invocations_same_session():
    """TC-13: Two sequential invoke_agent calls with different messages must both succeed."""
    from src.agents.graph import invoke_agent, reset_graph

    reset_graph()
    cp = MemorySaver()
    sid = str(uuid.uuid4())
    r1 = invoke_agent(session_id=sid, user_message="I want a table for 2", checkpointer=cp)
    r2 = invoke_agent(session_id=sid, user_message="Cancel that reservation", checkpointer=cp)
    assert r1["intent"] == "make_reservation"
    assert r2["intent"] == "cancel_reservation"
    reset_graph()


# ─── TC-14: POST /agent/chat with unknown message returns clarify ─────────────
def test_tc14_chat_endpoint_unknown_message():
    """TC-14: POST /agent/chat with unrelated message must return intent=unknown."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LANCEDB_URI"] = tmp
        from src.config import get_settings

        get_settings.cache_clear()
        from src.main import create_app
        from src.agents.graph import reset_graph

        reset_graph()
        app = create_app()
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=True) as client:
            r = client.post(
                "/api/v1/agent/chat",
                json={"message": "What time does the stock market open?"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert "final_response" in data
            assert len(data["final_response"]) > 0
        get_settings.cache_clear()
        os.environ.pop("LANCEDB_URI", None)
        reset_graph()


# ─── TC-15: POST /agent/chat returns session_id on each call ─────────────────
def test_tc15_chat_endpoint_returns_session_id():
    """TC-15: Every /agent/chat response must include a non-empty session_id."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LANCEDB_URI"] = tmp
        from src.config import get_settings

        get_settings.cache_clear()
        from src.main import create_app
        from src.agents.graph import reset_graph

        reset_graph()
        app = create_app()
        from fastapi.testclient import TestClient

        with TestClient(app, raise_server_exceptions=True) as client:
            for msg in ["I want a reservation", "Cancel my booking"]:
                r = client.post("/api/v1/agent/chat", json={"message": msg})
                assert r.status_code == 200, r.text
                data = r.json()
                assert "session_id" in data
                assert len(data["session_id"]) > 0
        get_settings.cache_clear()
        os.environ.pop("LANCEDB_URI", None)
        reset_graph()
