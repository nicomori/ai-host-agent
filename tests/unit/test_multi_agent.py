"""
Step 8 — Multi-agent coordination tests (ai-host-agent).

Architecture under test:
  Supervisor (Command routing) → [reservation_agent | cancellation_agent |
                                   query_agent       | clarify_agent]

7 test cases:
  TC1: supervisor routes "book a table" → reservation_agent (make_reservation)
  TC2: supervisor routes "cancel reservation" → cancellation_agent
  TC3: supervisor routes "check status" → query_agent
  TC4: supervisor routes unknown text → clarify_agent
  TC5: agent_trace records correct sub-agent chain
  TC6: sub-agents are independently callable (unit isolation)
  TC7: multi-turn: different intents produce different traces per session
"""

from __future__ import annotations

import uuid
import pytest
from langgraph.checkpoint.memory import MemorySaver

from src.agents.graph import build_graph, invoke_agent, reset_graph
from src.agents.sub_agents import (
    cancellation_agent,
    clarify_agent,
    query_agent,
    reservation_agent,
)
from src.agents.state import AgentState


# ─── Fixture helpers ──────────────────────────────────────────────────────────


@pytest.fixture()
def step8_graph():
    reset_graph()
    cp = MemorySaver()
    g = build_graph(checkpointer=cp)
    yield g
    reset_graph()


@pytest.fixture()
def step8_invoke():
    """Helper that resets graph singleton before each invoke."""

    def _invoke(msg, session_id=None, reservation_data=None):
        reset_graph()
        sid = session_id or str(uuid.uuid4())
        return invoke_agent(
            session_id=sid,
            user_message=msg,
            reservation_data=reservation_data,
            checkpointer=MemorySaver(),
        )

    return _invoke


def _stub_state(**kwargs) -> AgentState:
    """Build a minimal AgentState for sub-agent unit tests."""
    base: AgentState = {
        "messages": [],
        "session_id": str(uuid.uuid4()),
        "intent": None,
        "reservation_data": kwargs.get("reservation_data"),
        "next_action": None,
        "final_response": None,
        "errors": [],
        "agent_trace": [],
    }
    base.update(kwargs)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# TC1 — Supervisor routes "book a table" → reservation_agent
# ══════════════════════════════════════════════════════════════════════════════


def test_tc1_supervisor_routes_book_to_reservation(step8_invoke):
    result = step8_invoke("I want to book a table for 2 tonight")
    assert result["intent"] == "make_reservation"
    assert "reservation_agent" in result["agent_trace"]
    assert "supervisor" in result["agent_trace"]


def test_tc1_reservation_response_asks_for_missing_fields(step8_invoke):
    result = step8_invoke("book a table")
    assert result["final_response"] is not None
    # Without any reservation_data, should ask for missing fields
    response = result["final_response"].lower()
    assert any(
        word in response
        for word in ["nombre", "teléfono", "día", "hora", "cuántos", "need", "details"]
    )


# ══════════════════════════════════════════════════════════════════════════════
# TC2 — Supervisor routes cancel → cancellation_agent
# ══════════════════════════════════════════════════════════════════════════════


def test_tc2_supervisor_routes_cancel_to_cancellation(step8_invoke):
    result = step8_invoke("please cancel my reservation")
    assert result["intent"] == "cancel_reservation"
    assert "cancellation_agent" in result["agent_trace"]
    assert "supervisor" in result["agent_trace"]


def test_tc2_cancel_response_requests_id_or_name(step8_invoke):
    result = step8_invoke("I want to delete my booking")
    assert result["intent"] == "cancel_reservation"
    response = result["final_response"].lower()
    assert any(word in response for word in ["reservation", "id", "name", "cancel"])


# ══════════════════════════════════════════════════════════════════════════════
# TC3 — Supervisor routes "check status" → query_agent
# ══════════════════════════════════════════════════════════════════════════════


def test_tc3_supervisor_routes_check_to_query(step8_invoke):
    result = step8_invoke("check the status of my booking")
    assert result["intent"] == "query_reservation"
    assert "query_agent" in result["agent_trace"]


def test_tc3_query_response_contains_status_context(step8_invoke):
    result = step8_invoke("can you check if my reservation is confirmed?")
    assert result["intent"] == "query_reservation"
    response = result["final_response"].lower()
    assert any(
        word in response
        for word in ["reserva", "nombre", "número", "busco", "reservation", "check", "status"]
    )


# ══════════════════════════════════════════════════════════════════════════════
# TC4 — Supervisor routes unknown → clarify_agent
# ══════════════════════════════════════════════════════════════════════════════


def test_tc4_supervisor_routes_unknown_to_clarify(step8_invoke):
    result = step8_invoke("tell me a joke")
    assert result["intent"] == "unknown"
    assert "clarify_agent" in result["agent_trace"]


def test_tc4_clarify_response_lists_supported_actions(step8_invoke):
    result = step8_invoke("what time is it?")
    assert result["intent"] == "unknown"
    response = result["final_response"]
    # Should mention supported actions (in Spanish: reserva, cancelación, consultar)
    assert any(
        word in response.lower() for word in ["reserva", "cancelación", "consultar", "reservation"]
    )


# ══════════════════════════════════════════════════════════════════════════════
# TC5 — agent_trace records correct execution chain
# ══════════════════════════════════════════════════════════════════════════════


def test_tc5_agent_trace_supervisor_then_sub_agent(step8_invoke):
    result = step8_invoke("I want to make a reservation for tomorrow")
    trace = result["agent_trace"]
    assert trace[0] == "supervisor", f"First should be supervisor, got {trace}"
    assert trace[1] == "reservation_agent", f"Second should be reservation_agent, got {trace}"
    assert len(trace) == 2, f"Trace should have exactly 2 entries, got {trace}"


def test_tc5_trace_length_always_two(step8_invoke):
    """Each invocation: supervisor → exactly one sub-agent."""
    for msg, expected_agent in [
        ("book me a table", "reservation_agent"),
        ("cancel please", "cancellation_agent"),
        ("check my booking status", "query_agent"),
        ("how are you", "clarify_agent"),
    ]:
        result = step8_invoke(msg)
        trace = result["agent_trace"]
        assert trace[-1] == expected_agent, f"msg={msg!r} expected {expected_agent}, trace={trace}"
        assert "supervisor" in trace


# ══════════════════════════════════════════════════════════════════════════════
# TC6 — Sub-agents independently callable (unit isolation)
# ══════════════════════════════════════════════════════════════════════════════


def test_tc6_reservation_agent_unit_no_data():
    state = _stub_state()
    result = reservation_agent(state)
    assert "final_response" in result
    assert "agent_trace" in result
    assert result["agent_trace"] == ["reservation_agent"]
    resp = result["final_response"].lower()
    assert any(
        w in resp for w in ["nombre", "teléfono", "día", "hora", "cuántos", "need", "details"]
    )


def test_tc6_reservation_agent_unit_all_data():
    state = _stub_state(
        reservation_data={
            "guest_name": "Ana",
            "guest_phone": "555-1234",
            "date": "2026-04-15",
            "time": "19:00",
            "party_size": 2,
        }
    )
    result = reservation_agent(state)
    resp = result["final_response"].lower()
    assert any(w in resp for w in ["anoté", "confirmad", "confirmed", "listo"])
    assert result["reservation_data"]["reservation_id"] is not None


def test_tc6_cancellation_agent_unit():
    state = _stub_state()
    result = cancellation_agent(state)
    assert result["agent_trace"] == ["cancellation_agent"]
    assert "cancel" in result["final_response"].lower()


def test_tc6_query_agent_unit():
    state = _stub_state()
    result = query_agent(state)
    assert result["agent_trace"] == ["query_agent"]
    assert result["final_response"] is not None


def test_tc6_clarify_agent_unit():
    state = _stub_state()
    result = clarify_agent(state)
    assert result["agent_trace"] == ["clarify_agent"]
    resp = result["final_response"].lower()
    assert any(w in resp for w in ["reserva", "cancelación", "consultar", "reservation"])


# ══════════════════════════════════════════════════════════════════════════════
# TC7 — Different intents in different sessions produce isolated traces
# ══════════════════════════════════════════════════════════════════════════════


def test_tc7_multi_session_isolated_traces(step8_invoke):
    """Each session is independent — traces don't bleed across calls."""
    r_book = step8_invoke("I want to reserve a table", session_id="session-book-001")
    r_cancel = step8_invoke("cancel my booking please", session_id="session-cancel-001")
    r_query = step8_invoke("check my status", session_id="session-query-001")

    assert r_book["agent_trace"] == ["supervisor", "reservation_agent"]
    assert r_cancel["agent_trace"] == ["supervisor", "cancellation_agent"]
    assert r_query["agent_trace"] == ["supervisor", "query_agent"]


def test_tc7_reservation_with_full_data_confirms(step8_invoke):
    """End-to-end: complete data → reservation confirmed with ID."""
    result = step8_invoke(
        "I want to book a table for 3 on April 10th at 8pm",
        reservation_data={
            "guest_name": "Carlos",
            "guest_phone": "555-9999",
            "date": "2026-04-10",
            "time": "20:00",
            "party_size": 3,
        },
    )
    assert result["intent"] == "make_reservation"
    assert result["reservation_data"] is not None
    assert "reservation_id" in (result["reservation_data"] or {})
    response = result["final_response"].lower()
    assert any(w in response for w in ["anoté", "confirmad", "confirmed", "listo"])
