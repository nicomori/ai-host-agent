"""
HostAI — AgentState definition (Step 5).

The state is a TypedDict that flows through every node of the LangGraph graph.
All fields use reducers so concurrent node updates are safe.
"""
from __future__ import annotations

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage


class ReservationData(TypedDict, total=False):
    """Structured data extracted by the agent during the conversation."""
    guest_name: str
    guest_phone: str
    date: str            # YYYY-MM-DD
    time: str            # HH:MM
    party_size: int
    notes: str
    reservation_id: str


class AgentState(TypedDict):
    """
    Full state for the HostAI conversation graph.

    Reducers:
      - messages: append-only (operator.add)
      - errors: append-only

    Single-writer fields (last-write-wins, no reducer needed):
      - session_id, intent, reservation_data, next_action, final_response
    """
    # Conversation history — append-only via operator.add
    messages: Annotated[list[BaseMessage], operator.add]

    # Session identity (set once at graph start)
    session_id: str

    # Intent detected by the classifier node
    # Values: "make_reservation" | "cancel_reservation" | "query_reservation" | "unknown"
    intent: Optional[str]

    # Structured reservation data extracted during conversation
    reservation_data: Optional[ReservationData]

    # Control flow: which node should run next after a decision node
    next_action: Optional[str]

    # Final text response to send back to the caller
    final_response: Optional[str]

    # Errors accumulated (append-only)
    errors: Annotated[list[str], operator.add]

    # Step 8: Agent execution trace — which sub-agents were invoked (append-only)
    agent_trace: Annotated[list[str], operator.add]
