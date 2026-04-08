"""
HostAI — LangGraph multi-agent conversation graph (Steps 5-8).

Step 8 — Multi-agent coordination:
  Architecture: Supervisor → Sub-agents (Command-based routing)

  Graph flow:
    START → supervisor → [reservation_agent | cancellation_agent |
                          query_agent       | clarify_agent      ] → END

  Key patterns:
    - Supervisor node returns Command(goto=target, update={...}) for routing.
      This replaces add_conditional_edges — the Command carries both the
      state update AND the routing decision atomically.
    - Sub-agents (sub_agents.py) are specialized nodes, independently testable.
    - agent_trace list accumulates which agents ran (for observability).
    - Context window managed at supervisor level (Step 7 integration).

Checkpointing (Step 6):
  - dev:  SqliteSaver → data/checkpoints.sqlite
  - prod: PostgresSaver (configured via CHECKPOINT_DB_PATH or PG DSN)
  - Each session uses thread_id = session_id — state persists across turns.
"""
from __future__ import annotations

import uuid
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from src.agents.state import AgentState, ReservationData
from src.agents.sub_agents import (
    cancellation_agent,
    clarify_agent,
    query_agent,
    reservation_agent,
)
from src.context_window import HOST_AGENT_BUDGET, apply_context_strategy
from src.guardrails import GuardrailsConfig, apply_input_guardrails, apply_output_guardrails
from src.observability import flush_traces, observe_fn, get_langfuse_client

# ─── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sos el host de La Trattoria. Hablás como una persona real, cálida y profesional — nunca como un robot.

Tu trabajo es atender llamadas telefónicas para:
- Tomar reservas (necesitás: nombre, teléfono, fecha, hora, cantidad de comensales)
- Cancelar reservas
- Consultar el estado de una reserva

Al tomar una reserva, ofrecé las secciones disponibles del restaurante:
- Patio (mesas al aire libre)
- Window (mesas junto a la ventana)
- Bar (mesas en la barra)
- Private (salones privados para grupos grandes)
- Booth (reservados)
- Quiet (zona tranquila)
Preguntá: "¿Tenés alguna preferencia de ubicación? Tenemos patio, ventana, barra, reservado..."
Si el cliente pide una sección, verificá disponibilidad para esa fecha y hora antes de confirmar.

Reglas de estilo:
- Hablá de forma natural, como si estuvieras en persona. Usá frases cortas.
- NUNCA uses listas con números o bullets. NUNCA uses formato tipo "Nombre: X / Fecha: Y".
- Confirmá los datos de forma conversacional: "Perfecto, te anoto a Juan para el viernes a las 9 de la noche, mesa para 4 en el patio."
- Si te faltan datos, pedilos de a uno, no todos juntos.
- Usá muletillas naturales: "dale", "perfecto", "genial", "listo".
- Siempre respondé en español rioplatense (vos, tenés, etc.)."""

# ─── Sub-agent targets (type alias for Command routing) ───────────────────────

_SubAgent = Literal[
    "reservation_agent",
    "cancellation_agent",
    "query_agent",
    "clarify_agent",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SUPERVISOR NODE (Step 8 — Multi-agent)
# ═══════════════════════════════════════════════════════════════════════════════

import re

_TARGET_MAP: dict[str, _SubAgent] = {
    "make_reservation":    "reservation_agent",
    "cancel_reservation":  "cancellation_agent",
    "query_reservation":   "query_agent",
    "unknown":             "clarify_agent",
}

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _keyword_classify(text: str) -> tuple[str, _SubAgent]:
    t = text.lower()
    if any(k in t for k in ["cancel", "cancela", "delete", "remove", "borrar", "disdire", "annulla"]):
        return "cancel_reservation", "cancellation_agent"
    if any(k in t for k in ["status", "estado", "confirma", "check", "lookup", "stato", "verifica", "conferma"]):
        return "query_reservation", "query_agent"
    if any(k in t for k in ["reserv", "book", "mesa", "table", "quiero", "want", "make",
                             "prenot", "tavolo", "posto", "vorrei", "voglio", "posto"]):
        return "make_reservation", "reservation_agent"
    return "unknown", "clarify_agent"


def _regex_extract(text: str) -> dict:
    """Extract reservation fields from free-form text using regex."""
    extracted: dict = {}

    # Phone: +39331234567 / 0039... / plain digits 10+
    phone_m = re.search(r"(\+?\d[\d\s\-]{8,}\d)", text)
    if phone_m:
        extracted["guest_phone"] = re.sub(r"[\s\-]", "", phone_m.group(1))

    # ISO date: 2026-04-15
    iso_m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if iso_m:
        extracted["date"] = iso_m.group(1)
    else:
        # "April 15" / "15 April" / "April 15th"
        for month_name, month_num in _MONTH_MAP.items():
            m = re.search(
                rf"\b{month_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b"
                rf"|\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{month_name}\b",
                text, re.IGNORECASE,
            )
            if m:
                day = (m.group(1) or m.group(2)).zfill(2)
                year = re.search(r"\b(202\d)\b", text)
                y = year.group(1) if year else "2026"
                extracted["date"] = f"{y}-{month_num}-{day}"
                break

    # Time: "8pm" / "20:00" / "8:30 pm"
    time_m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text, re.IGNORECASE)
    if time_m:
        h, mn, ampm = int(time_m.group(1)), int(time_m.group(2) or 0), time_m.group(3).lower()
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        extracted["time"] = f"{h:02d}:{mn:02d}"
    else:
        hhmm = re.search(r"\b(\d{2}):(\d{2})\b", text)
        if hhmm:
            extracted["time"] = f"{hhmm.group(1)}:{hhmm.group(2)}"

    # Party size: "for 3" / "3 people" / "party of 2" / "2 guests"
    ps_m = re.search(
        r"\bfor\s+(\d+)\b|\b(\d+)\s+(?:people|persons?|guests?|pax)\b"
        r"|\bparty\s+of\s+(\d+)\b|\btable\s+for\s+(\d+)\b",
        text, re.IGNORECASE,
    )
    if ps_m:
        val = next(g for g in ps_m.groups() if g is not None)
        extracted["party_size"] = int(val)

    # Guest name: "my name is X Y" / "name: X Y" / "i'm X Y"
    name_m = re.search(
        r"(?:my name is|name\s*[:\-]?|i(?:'m| am))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        text,
    )
    if name_m:
        extracted["guest_name"] = name_m.group(1).strip()

    return extracted


_LLM_SUPERVISOR_PROMPT = """Sos un supervisor de reservas de restaurante. Analizá el mensaje del usuario y respondé SOLO con un objeto JSON plano — sin markdown, sin code fences, sin explicación.

Claves requeridas (usá null si no está presente):
- intent: "make_reservation" | "cancel_reservation" | "query_reservation" | "unknown"
- guest_name: nombre completo string o null
- guest_phone: teléfono con código de país string o null
- date: YYYY-MM-DD string o null (hoy es {today})
- time: HH:MM formato 24h string o null
- party_size: entero o null
- reservation_id: UUID string o null

Ejemplo de salida (JSON crudo, sin backticks):
{{"intent":"make_reservation","guest_name":"Sofia Esposito","guest_phone":"+54911555012","date":"2026-04-15","time":"20:00","party_size":3,"reservation_id":null}}"""


def _llm_extract(text: str, existing_data: dict) -> tuple[str, _SubAgent, dict]:
    """Use Claude to classify intent and extract fields. Falls back to regex on error."""
    import os
    import json as _json
    from datetime import date as _date

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key.startswith("sk-nicolas"):
        return _regex_fallback(text, existing_data)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        today = str(_date.today())
        prompt = _LLM_SUPERVISOR_PROMPT.format(today=today)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=prompt,
            messages=[{"role": "user", "content": text}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = _json.loads(raw.strip())

        intent = parsed.get("intent", "unknown")
        target = _TARGET_MAP.get(intent, "clarify_agent")
        extracted = {k: v for k, v in parsed.items() if k != "intent" and v is not None}
        merged = {**existing_data, **extracted}
        return intent, target, merged
    except Exception:
        return _regex_fallback(text, existing_data)


def _regex_fallback(text: str, existing_data: dict) -> tuple[str, _SubAgent, dict]:
    intent, target = _keyword_classify(text)
    extracted = _regex_extract(text)
    return intent, target, {**existing_data, **extracted}


_INTENT_LABEL = {
    "make_reservation": "Nueva reserva",
    "cancel_reservation": "Cancelar reserva",
    "query_reservation": "Consultar reserva",
    "unknown": "Intento no identificado",
}


def _emit_supervisor_span(user_text, prior_intent, existing_data, intent, target, merged_data):
    """Create a descriptive Langfuse span for the supervisor decision."""
    client = get_langfuse_client()
    if not client:
        return
    try:
        from src.agents.sub_agents import _current_trace_id
        ctx = {"trace_id": _current_trace_id, "parent_span_id": ""} if _current_trace_id else None
        label = _INTENT_LABEL.get(intent, intent)
        span = client.start_observation(
            name=f"[HostAI] - Clasificador → {label} → {target}",
            as_type="agent",
            input={
                "mensaje_usuario": user_text[:200],
                "intent_previo": prior_intent,
                "datos_existentes": existing_data,
            },
            trace_context=ctx,
        )
        span.update(output={
            "intent_detectado": intent,
            "agente_destino": target,
            "campos_extraídos": list(merged_data.keys()) if merged_data else [],
            "datos_merged": merged_data,
        })
        span.end()
    except Exception:
        pass


def node_supervisor(state: AgentState) -> Command[_SubAgent]:
    messages = state.get("messages") or []
    messages, _alert = apply_context_strategy(messages, HOST_AGENT_BUDGET)
    existing_data = state.get("reservation_data") or {}
    prior_intent = state.get("intent")

    last_msg = messages[-1] if messages else None
    user_text = last_msg.content if last_msg and isinstance(last_msg.content, str) else ""

    if not last_msg:
        _emit_supervisor_span(user_text, prior_intent, existing_data, "unknown", "clarify_agent", {})
        return Command(goto="clarify_agent", update={"intent": "unknown", "next_action": "clarify"})

    # If we have a prior intent with incomplete data, continue that flow
    if prior_intent and prior_intent != "unknown" and existing_data:
        intent_kw, target_kw = _keyword_classify(user_text)
        regex_fields = _regex_extract(user_text)
        if intent_kw != "unknown" and intent_kw != prior_intent:
            intent, target, merged_data = _llm_extract(user_text, existing_data)
        else:
            _, _, merged_data = _llm_extract(user_text, existing_data)
            intent = prior_intent
            target = _TARGET_MAP.get(intent, "clarify_agent")
    else:
        intent, target, merged_data = _llm_extract(user_text, existing_data)

    _emit_supervisor_span(user_text, prior_intent, existing_data, intent, target, merged_data)

    return Command(
        goto=target,
        update={
            "intent": intent,
            "next_action": intent,
            "reservation_data": merged_data,
            "agent_trace": ["supervisor"],
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph(checkpointer=None):
    """
    Build and compile the HostAI multi-agent conversation graph.

    Step 8 architecture:
      START → supervisor (Command routing) →
        reservation_agent  → END
        cancellation_agent → END
        query_agent        → END
        clarify_agent      → END

    No conditional edges needed — supervisor's Command(goto=...) handles routing.
    """
    g = StateGraph(AgentState)

    # Supervisor (orchestrator) — uses Command for routing
    g.add_node("supervisor", node_supervisor)

    # Specialized sub-agents (from sub_agents.py)
    g.add_node("reservation_agent", reservation_agent)
    g.add_node("cancellation_agent", cancellation_agent)
    g.add_node("query_agent", query_agent)
    g.add_node("clarify_agent", clarify_agent)

    # Entry: START → supervisor
    g.add_edge(START, "supervisor")

    # Termination edges for all sub-agents
    g.add_edge("reservation_agent", END)
    g.add_edge("cancellation_agent", END)
    g.add_edge("query_agent", END)
    g.add_edge("clarify_agent", END)

    # Step 6: default to SqliteSaver for dev persistence; tests pass MemorySaver
    if checkpointer is not None:
        cp = checkpointer
    else:
        try:
            from src.checkpointing import get_checkpointer, CHECKPOINT_DB_PATH
            cp = get_checkpointer(use_sqlite=True, db_path=CHECKPOINT_DB_PATH)
        except Exception:
            cp = MemorySaver()
    return g.compile(checkpointer=cp)


# ─── Singleton graph ──────────────────────────────────────────────────────────
_graph = None


def get_graph(checkpointer=None):
    """Return the compiled graph, building it lazily."""
    global _graph
    if _graph is None:
        _graph = build_graph(checkpointer=checkpointer)
    return _graph


def reset_graph():
    """Reset singleton — used in tests."""
    global _graph
    _graph = None
    from src.api.routes import reset_routes
    reset_routes()


# ─── Public invoke helper ─────────────────────────────────────────────────────

def invoke_agent(
    session_id: str,
    user_message: str,
    reservation_data: Optional[dict] = None,
    checkpointer=None,
    guardrails_config: Optional[GuardrailsConfig] = None,
) -> dict:
    """
    Single-turn invoke of the HostAI multi-agent graph.

    Args:
        session_id:        Unique conversation ID (maps to LangGraph thread_id).
        user_message:      Raw text from the guest.
        reservation_data:  Any already-collected reservation fields.
        checkpointer:      Optional checkpointer override.
        guardrails_config: Optional guardrails configuration (uses defaults if None).

    Returns:
        Dict with: final_response, intent, reservation_data, messages, agent_trace

    Raises:
        GuardrailViolation: if input fails safety checks.
    """
    # Step 9: apply input guardrails before touching the graph
    cfg = guardrails_config or GuardrailsConfig()
    safe_message = apply_input_guardrails(user_message, cfg)

    graph = get_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": session_id}}

    # Load prior checkpoint to preserve conversation context across turns
    prior_reservation_data = None
    prior_intent = None
    has_prior = False
    try:
        snapshot = graph.get_state(config)
        if snapshot and snapshot.values and snapshot.values.get("messages"):
            has_prior = True
            prior_reservation_data = snapshot.values.get("reservation_data")
            prior_intent = snapshot.values.get("intent")
    except Exception:
        pass

    if has_prior:
        # Continuing conversation — only send the new message.
        # Messages reducer (operator.add) appends to checkpoint history.
        # Preserve reservation_data and intent from checkpoint.
        merged_data = {**(prior_reservation_data or {}), **(reservation_data or {})}
        initial_state: AgentState = {
            "messages": [HumanMessage(content=safe_message)],
            "session_id": session_id,
            "intent": prior_intent,
            "reservation_data": merged_data or None,
            "next_action": None,
            "final_response": None,
            "errors": [],
            "agent_trace": [],
        }
    else:
        # First message in session — include system prompt
        initial_state: AgentState = {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=safe_message),
            ],
            "session_id": session_id,
            "intent": None,
            "reservation_data": reservation_data,
            "next_action": None,
            "final_response": None,
            "errors": [],
            "agent_trace": [],
        }
    # Step 11: create Langfuse root span and propagate trace_id
    lf_client = get_langfuse_client()
    root_span = None
    if lf_client:
        try:
            msg_preview = user_message[:50].replace("\n", " ")
            root_span = lf_client.start_observation(
                name=f"[HostAI] - HostAI — \"{msg_preview}\"",
                as_type="chain",
                input={
                    "session_id": session_id,
                    "mensaje_usuario": user_message,
                    "datos_previos": reservation_data,
                    "turno": "continuación" if has_prior else "inicio",
                },
            )
            from src.agents.sub_agents import set_trace_id
            set_trace_id(root_span.trace_id)
        except Exception:
            pass

    result = graph.invoke(initial_state, config=config)

    # Update root span with result and flush
    if root_span:
        try:
            intent = result.get("intent", "unknown")
            label = _INTENT_LABEL.get(intent, intent)
            root_span.update(
                name=f"[HostAI] - HostAI — {label} — \"{user_message[:40]}\"",
                output={
                    "intent": intent,
                    "respuesta": result.get("final_response", ""),
                    "datos_reserva": result.get("reservation_data"),
                    "agentes_ejecutados": result.get("agent_trace", []),
                },
            )
            root_span.end()
        except Exception:
            pass
    flush_traces()

    # Step 9: apply output guardrails (validate + PII mask) before returning
    raw_response = result.get("final_response", "")
    safe_response = apply_output_guardrails(raw_response, cfg) if raw_response else raw_response

    return {
        "final_response": safe_response,
        "intent": result.get("intent"),
        "reservation_data": result.get("reservation_data"),
        "messages": result.get("messages", []),
        "agent_trace": result.get("agent_trace", []),
    }
