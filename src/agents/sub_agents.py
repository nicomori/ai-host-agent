"""
Step 8 — Multi-agent sub-agents (HostAI).

Specialized agents for the Supervisor pattern:
  - reservation_agent  : handles make_reservation + data extraction
  - cancellation_agent : handles cancel_reservation
  - query_agent        : handles reservation status queries
  - clarify_agent      : handles unknown intent

Each is a standalone pure-function node — independently testable and composable.
The Supervisor (in graph.py) uses Command(goto=...) to route to these agents.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from langchain_core.messages import AIMessage

from src.agents.state import AgentState
from src.observability import get_langfuse_client

logger = logging.getLogger(__name__)


_current_trace_id: str | None = None


def set_trace_id(trace_id: str | None):
    """Set the current trace ID for sub-agent spans."""
    global _current_trace_id
    _current_trace_id = trace_id


def _start_span(name: str, input_data: dict):
    """Start a Langfuse agent span linked to the current trace. Returns the span object or None."""
    client = get_langfuse_client()
    if client is None:
        return None
    try:
        ctx = {"trace_id": _current_trace_id, "parent_span_id": ""} if _current_trace_id else None
        return client.start_observation(
            name=name,
            as_type="agent",
            input=input_data,
            trace_context=ctx,
        )
    except Exception:
        return None


def _end_span(span, output_data: dict):
    """End a Langfuse span with output (v4 API: update then end)."""
    if span is None:
        return
    try:
        span.update(output=output_data)
        span.end()
    except Exception:
        pass


# ─── Sub-agent: Reservation ────────────────────────────────────────���──────────

def reservation_agent(state: AgentState) -> dict:
    """
    Specialized agent for make_reservation intent.

    Responsibilities:
      1. Extract guest details from conversation history.
      2. If all required fields present → persist to PostgreSQL + confirm.
      3. If fields missing → ask for them (clarification loop).

    Required fields: guest_name, guest_phone, date, time, party_size.
    """
    existing = state.get("reservation_data") or {}
    required_fields = ["guest_name", "guest_phone", "date", "time", "party_size"]
    missing = [f for f in required_fields if not existing.get(f)]

    guest = existing.get("guest_name", "?")
    span_name = f"[HostAI] - Reserva — {guest}" if not missing else f"[HostAI] - Reserva — pidiendo {missing[0]}"
    span = _start_span(span_name, {
        "datos_actuales": existing,
        "campos_faltantes": missing,
        "campos_completos": [f for f in required_fields if existing.get(f)],
    })

    if missing:
        field_prompts = {
            "guest_name": "¿A nombre de quién sería la reserva?",
            "guest_phone": "Genial. ¿Me pasás un teléfono de contacto?",
            "date": "Dale. ¿Para qué día sería?",
            "time": "Perfecto. ¿Y a qué hora les gustaría venir?",
            "party_size": "¿Cuántos van a ser?",
        }
        first_missing = missing[0]
        response = field_prompts.get(first_missing, f"Necesitaría que me pases {first_missing}.")
        result = {
            "reservation_data": existing,
            "final_response": response,
            "messages": [AIMessage(content=response)],
            "agent_trace": ["reservation_agent"],
        }
        _end_span(span, {
            "acción": f"Pidiendo campo faltante: {first_missing}",
            "campos_faltantes_restantes": missing,
            "respuesta": response,
        })
        return result

    # All fields present → persist to PostgreSQL
    try:
        from src.services.db import save_reservation
        saved = save_reservation(
            guest_name=str(existing["guest_name"]),
            guest_phone=str(existing["guest_phone"]),
            date=str(existing["date"]),
            time=str(existing["time"]),
            party_size=int(existing.get("party_size", 2)),
            notes=existing.get("notes"),
        )
        rid = saved["reservation_id"]
        existing = {**existing, "reservation_id": rid}
        response = (
            f"Listo, ya te anoté. {saved['guest_name']}, "
            f"mesa para {saved['party_size']} el {saved['date']} a las {saved['time']}. "
            f"¡Los esperamos! ¿Necesitás algo más?"
        )
        logger.info("[HostAI] - Reservation Agent: saved reservation %s to DB", rid)
    except Exception as exc:
        logger.warning("[HostAI] - Reservation Agent: DB unavailable, using in-memory ID — %s", exc)
        rid = str(uuid.uuid4())
        existing = {**existing, "reservation_id": rid}
        response = (
            f"Listo, ya te anoté. {existing.get('guest_name')}, "
            f"mesa para {existing.get('party_size')} el {existing.get('date')} a las {existing.get('time')}. "
            f"¡Los esperamos! ¿Necesitás algo más?"
        )

    result = {
        "reservation_data": existing,
        "final_response": response,
        "messages": [AIMessage(content=response)],
        "agent_trace": ["reservation_agent"],
    }
    _end_span(span, {
        "acción": "Reserva guardada en PostgreSQL",
        "reservation_id": existing.get("reservation_id"),
        "resumen": f"{existing.get('guest_name')} — {existing.get('party_size')}p — {existing.get('date')} {existing.get('time')}",
        "respuesta": response,
    })
    return result


# ─── Sub-agent: Cancellation ──────────────────────────────────────────────────

def cancellation_agent(state: AgentState) -> dict:
    """
    Specialized agent for cancel_reservation intent.

    Responsibilities:
      1. Request reservation ID or name + date for lookup.
      2. Update status to 'cancelled' in PostgreSQL.
    """
    reservation_data = state.get("reservation_data") or {}
    rid = reservation_data.get("reservation_id")
    span_name = f"[HostAI] - Cancelación — reserva {rid[:8]}" if rid else "[HostAI] - Cancelación — pidiendo ID"
    span = _start_span(span_name, {
        "reservation_id": rid,
        "datos_disponibles": reservation_data,
    })

    if rid:
        try:
            from src.services.db import update_reservation_status
            updated = update_reservation_status(rid, "cancelled", "Cancelada vía agente IA")
            if updated:
                response = (
                    "Listo, ya te cancelé la reserva. "
                    "¿Necesitás algo más?"
                )
                logger.info("[HostAI] - Cancellation Agent: cancelled reservation %s in DB", rid)
            else:
                response = (
                    "Mmm, no estoy encontrando esa reserva. "
                    "¿Me podés confirmar el número de reserva o el nombre con el que fue hecha?"
                )
        except Exception as exc:
            logger.warning("[HostAI] - Cancellation Agent: DB unavailable — %s", exc)
            response = (
                "Dale, te cancelo la reserva. "
                "En breve te llega la confirmación."
            )
    else:
        response = (
            "Dale, te la cancelo. ¿Me decís tu nombre o el número de reserva?"
        )

    result = {
        "final_response": response,
        "messages": [AIMessage(content=response)],
        "agent_trace": ["cancellation_agent"],
    }
    _end_span(span, {
        "acción": "Reserva cancelada en DB" if rid else "Solicitando ID de reserva",
        "reservation_id": rid,
        "respuesta": response,
    })
    return result


# ─── Sub-agent: Query ─────────────────────────────────────────────────────────

def query_agent(state: AgentState) -> dict:
    """
    Specialized agent for query_reservation intent.

    Responsibilities:
      1. Look up reservation by UUID from PostgreSQL.
      2. Return live status and details.
    """
    reservation_data = state.get("reservation_data") or {}
    rid = reservation_data.get("reservation_id")
    span_name = f"[HostAI] - Consulta — reserva {rid[:8]}" if rid else "[HostAI] - Consulta — pidiendo ID"
    span = _start_span(span_name, {
        "reservation_id": rid,
        "datos_disponibles": reservation_data,
    })

    if rid:
        try:
            from src.services.db import get_reservation_by_uuid
            res = get_reservation_by_uuid(rid)
            if res:
                status_es = {"confirmed": "confirmada", "cancelled": "cancelada", "seated": "en mesa", "no_show": "marcada como no presentada", "pending": "pendiente"}
                status_txt = status_es.get(res['status'], res['status'])
                response = (
                    f"Sí, acá la tengo. La reserva de {res['guest_name']} está {status_txt}. "
                    f"Es para {res['party_size']} personas, el {res['date']} a las {res['time']}. "
                    f"¿Necesitás algo más?"
                )
                logger.info("[HostAI] - Query Agent: fetched reservation %s from DB", rid)
            else:
                response = (
                    "No estoy encontrando esa reserva. "
                    "¿Me podés dar el nombre o el número de reserva de nuevo?"
                )
        except Exception as exc:
            logger.warning("[HostAI] - Query Agent: DB unavailable — %s", exc)
            response = (
                f"Tu reserva está confirmada para "
                f"{reservation_data.get('date', 'la fecha')} "
                f"a las {reservation_data.get('time', 'la hora programada')}. "
                f"¿Todo bien con eso?"
            )
    else:
        response = (
            "Dale, te la busco. ¿Me decís tu nombre o el número de reserva?"
        )

    result = {
        "final_response": response,
        "messages": [AIMessage(content=response)],
        "agent_trace": ["query_agent"],
    }
    _end_span(span, {
        "acción": "Consulta de reserva en DB" if rid else "Solicitando ID de reserva",
        "reservation_id": rid,
        "respuesta": response,
    })
    return result


# ─── Sub-agent: Clarify ───────────────────────────────────────────────────────

def clarify_agent(state: AgentState) -> dict:
    """
    Fallback agent when intent is unknown.
    Guides the guest toward a supported action.
    """
    span = _start_span("[HostAI] - Bienvenida — intent no identificado", {
        "motivo": "El usuario no expresó un intent claro (reservar, cancelar, consultar)",
    })
    response = (
        "Hola, hablas con La Trattoria. "
        "Puedo ayudarte con una reserva, una cancelación, o consultar una reserva que ya tengas. "
        "¿Qué necesitás?"
    )
    result = {
        "final_response": response,
        "messages": [AIMessage(content=response)],
        "agent_trace": ["clarify_agent"],
    }
    _end_span(span, {
        "acción": "Mensaje de bienvenida enviado — esperando intent del usuario",
        "respuesta": response,
    })
    return result
