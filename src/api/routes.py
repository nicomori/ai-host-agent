"""HostAI API — Reservations + Voice + Agent + SSE streaming endpoints.
NOTE: Using Optional[X] instead of X | None for Python 3.9 compatibility.
Resolution Form 1: Replace union pipe syntax with Optional[] from typing.

Step 13 additions:
  - API key authentication on mutation endpoints
  - GET /reservations/stream — Server-Sent Events for live reservation updates

Step N+1 — PostgreSQL persistence:
  - All reads/writes go to PostgreSQL via pg_db module
  - _reservations in-memory dict removed (state survives restart)
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Security, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from twilio.twiml.voice_response import Gather, VoiceResponse

from src.api.auth import verify_api_key
from src.config import AppSettings, get_settings
from src.services import db as pg_db
from src.models.floor_plan import AssignmentsForHour, TableAssignmentResponse
from src.services import floor_plan_service
from src.api.auth_users import get_current_user, UserInfo
from src.models.reservation import (
    CancelReservationRequest,
    CancelReservationResponse,
    CreateReservationRequest,
    CreateReservationResponse,
    ReservationListResponse,
    ReservationResponse,
    ReservationStatus,
    VoiceOutboundResponse,
    CallStatus,
)

router = APIRouter()

SettingsDep = Annotated[AppSettings, Depends(get_settings)]


# ─── Request models ─────────────────────────────────────────────────────────


class UpdateStatusRequest(BaseModel):
    status: str


class AssignTableRequest(BaseModel):
    table_id: str
    reservation_id: str
    date: str
    hour: str


# Form 3: reset_routes() is a no-op in DB mode to avoid wiping real data.
def reset_routes() -> None:
    """No-op in DB persistence mode. State is managed by PostgreSQL."""
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_reservation_or_404(reservation_id: str) -> dict:
    row = pg_db.get_reservation_by_uuid(reservation_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reservation '{reservation_id}' not found",
        )
    return row


# ─── Reservations ──────────────────────────────────────────────────────────────


@router.get(
    "/reservations",
    response_model=ReservationListResponse,
    summary="List all reservations",
    tags=["Reservations"],
)
async def list_reservations(
    cfg: SettingsDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    status_filter: Optional[ReservationStatus] = Query(default=None, alias="status"),
) -> ReservationListResponse:
    all_rows = pg_db.list_reservations(
        status_filter=status_filter.value if status_filter else None,
    )
    total = len(all_rows)
    start = (page - 1) * page_size
    page_items = all_rows[start : start + page_size]
    return ReservationListResponse(
        reservations=[ReservationResponse(**r) for r in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/reservations",
    response_model=CreateReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reservation",
    tags=["Reservations"],
    dependencies=[Security(verify_api_key)],
)
async def create_reservation(
    body: CreateReservationRequest,
    cfg: SettingsDep,
) -> CreateReservationResponse:
    reservation_id = str(uuid.uuid4())
    minutes_before = cfg.yaml.reservations.confirmation_call_minutes_before

    pg_db.save_reservation(
        guest_name=body.guest_name,
        guest_phone=body.guest_phone,
        date=str(body.date),
        time=str(body.time),
        party_size=body.party_size,
        reservation_id=reservation_id,
        preference=body.preference,
        special_requests=body.special_requests,
        notes=body.notes,
    )

    return CreateReservationResponse(
        reservation_id=reservation_id,
        status=ReservationStatus.CONFIRMED,
        message=f"Reservation confirmed at {cfg.restaurant_name}. Confirmation call {minutes_before}min before.",
        confirmation_call_scheduled_at=_now_iso(),
    )


@router.get(
    "/reservations/stream",
    summary="Stream reservation updates via SSE",
    tags=["Streaming"],
    response_class=StreamingResponse,
)
async def stream_reservations(
    cfg: SettingsDep,
    once: bool = Query(default=False, description="Send snapshot then close (for testing)"),
) -> StreamingResponse:
    """
    Server-Sent Events stream for live reservation updates.
    Resolution Form 1: Placed BEFORE /{reservation_id} to avoid path-param shadowing.
    """

    async def event_generator():
        rows = pg_db.list_reservations()
        snapshot = {
            "event": "snapshot",
            "reservations": rows,
            "total": len(rows),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield f"data: {json.dumps(snapshot, default=str)}\n\n"
        if once:
            return
        while True:
            await asyncio.sleep(30)
            yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get a reservation by ID",
    tags=["Reservations"],
)
async def get_reservation(reservation_id: str, cfg: SettingsDep) -> ReservationResponse:
    record = _get_reservation_or_404(reservation_id)
    return ReservationResponse(**record)


@router.patch(
    "/reservations/{reservation_id}/status",
    summary="Update reservation status (seated, no_show, etc.)",
    tags=["Reservations"],
    dependencies=[Security(verify_api_key)],
)
async def update_reservation_status(
    reservation_id: str,
    body: UpdateStatusRequest,
    cfg: SettingsDep,
) -> dict:
    _get_reservation_or_404(reservation_id)
    new_status = body.status
    allowed = {"confirmed", "seated", "no_show", "cancelled"}
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {allowed}")
    pg_db.update_reservation_status(reservation_id=reservation_id, new_status=new_status)
    return {"reservation_id": reservation_id, "status": new_status}


@router.delete(
    "/reservations/{reservation_id}",
    response_model=CancelReservationResponse,
    summary="Cancel a reservation",
    tags=["Reservations"],
    dependencies=[Security(verify_api_key)],
)
async def cancel_reservation(
    reservation_id: str,
    body: CancelReservationRequest,
    cfg: SettingsDep,
) -> CancelReservationResponse:
    _get_reservation_or_404(reservation_id)  # raises 404 if not found
    window_hours = cfg.yaml.reservations.cancellation_window_hours
    pg_db.update_reservation_status(
        reservation_id=reservation_id,
        new_status="cancelled",
        notes=body.reason,
    )
    return CancelReservationResponse(
        reservation_id=reservation_id,
        status=ReservationStatus.CANCELLED,
        message=f"Reservation cancelled. Window was {window_hours}h.",
    )


# ─── Voice ────────────────────────────────────────────────────────────────────

_GOODBYE_SIGNALS = [
    "goodbye",
    "arrivederci",
    "thank you",
    "grazie",
    "see you",
    "a presto",
    "have a great",
    "buona serata",
    "enjoy your",
    "confirmed",
    "confirmed!",
    "anything else",
    "is there anything else",
    "adiós",
    "chau",
    "gracias",
    "hasta luego",
    "nos vemos",
    "confirmada",
    "algo más",
    "hay algo más",
    "reserva confirmada",
]


def _is_conversation_done(text: str) -> bool:
    t = text.lower()
    return any(sig in t for sig in _GOODBYE_SIGNALS)


def _make_twiml(speech: str, gather_action: str, language: str = "es-ES") -> str:
    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action=gather_action,
        method="POST",
        language=language,
        speech_timeout="auto",
        action_on_empty_result=True,
    )
    gather.say(speech, language=language)
    vr.append(gather)
    vr.say("No escuché nada. Lo llamaremos pronto.", language=language)
    return str(vr)


@router.post(
    "/voice/inbound",
    summary="Handle inbound Twilio call webhook",
    tags=["Voice"],
)
async def voice_inbound(
    request: Request,
    cfg: SettingsDep,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(default="ringing"),
):
    try:
        pg_db.save_call_log(
            call_sid=CallSid,
            from_number=From,
            to_number=To,
            call_status=CallStatus,
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "[HostAI] - Voice Inbound: failed to save call log for %s: %s", CallSid, exc
        )

    from src.services.voice_tts import synthesize as tts_synthesize

    process_url = f"{cfg.env.twilio_webhook_base_url}/api/v1/voice/process"
    base_url = cfg.env.twilio_webhook_base_url
    language = "es-ES"
    eleven_key = cfg.env.elevenlabs_api_key
    eleven_voice = cfg.env.elevenlabs_voice_id

    welcome = f"Hola, buenas, hablas con {cfg.restaurant_name}. ¿En qué te puedo ayudar?"

    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action=process_url,
        method="POST",
        language=language,
        speech_timeout="auto",
        action_on_empty_result=True,
    )

    if eleven_key and eleven_voice:
        try:
            uid = tts_synthesize(welcome, eleven_key, eleven_voice)
            gather.play(f"{base_url}/api/v1/audio/{uid}")
        except Exception:
            gather.say(welcome, language=language)
    else:
        gather.say(welcome, language=language)

    vr.append(gather)
    vr.say("No escuché nada. Lo llamaremos pronto.", language=language)
    return Response(content=str(vr), media_type="application/xml")


@router.post(
    "/voice/process",
    summary="Process speech input and return agent response as TwiML",
    tags=["Voice"],
)
async def voice_process(
    cfg: SettingsDep,
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    From: str = Form(default=""),
):
    from src.agents.graph import invoke_agent
    from src.services.voice_tts import synthesize as tts_synthesize

    process_url = f"{cfg.env.twilio_webhook_base_url}/api/v1/voice/process"
    base_url = cfg.env.twilio_webhook_base_url
    language = "es-ES"
    eleven_key = cfg.env.elevenlabs_api_key
    eleven_voice = cfg.env.elevenlabs_voice_id

    def _twiml_say_or_play(vr_or_gather, text: str):
        if eleven_key and eleven_voice:
            try:
                uid = tts_synthesize(text, eleven_key, eleven_voice)
                vr_or_gather.play(f"{base_url}/api/v1/audio/{uid}")
                return
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "[HostAI] - Voice TTS: ElevenLabs synthesis failed, falling back to Twilio TTS: %s",
                    exc,
                )
        vr_or_gather.say(text, language=language)

    if not SpeechResult.strip():
        vr = VoiceResponse()
        gather = Gather(
            input="speech",
            action=process_url,
            method="POST",
            language=language,
            speech_timeout="auto",
            action_on_empty_result=True,
        )
        _twiml_say_or_play(gather, "No te escuché. ¿Podés repetir?")
        vr.append(gather)
        return Response(content=str(vr), media_type="application/xml")

    result = invoke_agent(session_id=CallSid, user_message=SpeechResult)
    agent_text = result.get("final_response") or "Disculpá, no entendí tu pedido."

    vr = VoiceResponse()
    if _is_conversation_done(agent_text):
        _twiml_say_or_play(vr, agent_text)
        vr.hangup()
    else:
        gather = Gather(
            input="speech",
            action=process_url,
            method="POST",
            language=language,
            speech_timeout="auto",
            action_on_empty_result=True,
        )
        _twiml_say_or_play(gather, agent_text)
        vr.append(gather)
        # Fallback if no speech detected — redirect back to process with empty result
        vr.redirect(process_url, method="POST")

    return Response(content=str(vr), media_type="application/xml")


@router.get(
    "/audio/{uid}",
    summary="Serve generated TTS audio file",
    tags=["Voice"],
)
async def serve_audio(uid: str):
    from src.services.voice_tts import get_audio_path

    path = get_audio_path(uid)
    if not path:
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(str(path), media_type="audio/mpeg")


@router.post(
    "/voice/outbound/{reservation_id}",
    response_model=VoiceOutboundResponse,
    summary="Trigger outbound confirmation call",
    tags=["Voice"],
)
async def voice_outbound_confirmation(
    reservation_id: str,
    cfg: SettingsDep,
) -> VoiceOutboundResponse:
    from twilio.rest import Client as TwilioClient

    reservation = _get_reservation_or_404(reservation_id)
    sid = cfg.env.twilio_account_sid
    token = cfg.env.twilio_auth_token
    from_number = cfg.env.twilio_phone_number

    if not sid or not token or not from_number:
        raise HTTPException(status_code=503, detail="Twilio credentials not configured")

    client = TwilioClient(sid, token)
    guest_phone = reservation.get("guest_phone", "")
    guest_name = reservation.get("guest_name", "")
    date = reservation.get("date", "")
    time = reservation.get("time", "")
    party_size = reservation.get("party_size", "")

    twiml_msg = (
        f"<Response><Say language='es-ES'>"
        f"Hola {guest_name}. Te llamamos desde {cfg.restaurant_name} "
        f"para confirmar tu reserva de {party_size} personas "
        f"para el {date} a las {time}. ¡Te esperamos!"
        f"</Say></Response>"
    )
    call = client.calls.create(
        to=guest_phone,
        from_=from_number,
        twiml=twiml_msg,
    )
    pg_db.update_confirmation_status(reservation_id, "confirmed")
    return VoiceOutboundResponse(
        reservation_id=reservation_id,
        call_sid=call.sid,
        status=CallStatus.SCHEDULED,
        message=f"Outbound confirmation call initiated to {guest_phone}.",
    )


@router.patch(
    "/reservations/{reservation_id}/confirmation",
    summary="Update confirmation status without calling",
    tags=["Reservations"],
)
async def update_confirmation(
    reservation_id: str,
    body: UpdateStatusRequest,
    _key: str = Security(verify_api_key),
) -> dict:
    """Mark a reservation as confirmed/declined without a phone call."""
    _get_reservation_or_404(reservation_id)
    allowed = {"pending", "confirmed", "declined", "no_answer", "failed"}
    if body.status not in allowed:
        raise HTTPException(status_code=422, detail=f"confirmation status must be one of {allowed}")
    pg_db.update_confirmation_status(reservation_id, body.status)
    return {"reservation_id": reservation_id, "confirmation_status": body.status}


@router.get(
    "/config/confirmation",
    summary="Get confirmation call settings",
    tags=["Config"],
)
async def get_confirmation_config(cfg: SettingsDep) -> dict:
    return {"confirmation_call_minutes_before": cfg.reservations.confirmation_call_minutes_before}


@router.patch(
    "/config/confirmation",
    summary="Update confirmation call lead time (admin only)",
    tags=["Config"],
)
async def update_confirmation_config(
    body: dict,
    admin: UserInfo = Depends(get_current_user),
) -> dict:
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    minutes = body.get("confirmation_call_minutes_before")
    if minutes is None or not isinstance(minutes, int) or minutes < 5:
        raise HTTPException(
            status_code=422, detail="confirmation_call_minutes_before must be an integer >= 5"
        )
    import yaml

    config_path = os.path.join(os.path.dirname(__file__), "../../config.yaml")
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("reservations", {})["confirmation_call_minutes_before"] = minutes
    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)
    return {
        "confirmation_call_minutes_before": minutes,
        "message": "Config updated. Restart API to apply.",
    }


# ─── Agent ────────────────────────────────────────────────────────────────────


class AgentChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    reservation_data: Optional[dict] = None


class AgentChatResponse(BaseModel):
    session_id: str
    final_response: str
    intent: Optional[str] = None
    reservation_data: Optional[dict] = None


@router.post(
    "/agent/chat",
    response_model=AgentChatResponse,
    summary="Chat with the HostAI reservation agent",
    tags=["Agent"],
)
async def agent_chat(body: AgentChatRequest, cfg: SettingsDep) -> AgentChatResponse:
    from src.agents.graph import invoke_agent
    from src.observability import trace_session

    session_id = body.session_id or str(uuid.uuid4())
    with trace_session(session_id=session_id, user_message=body.message):
        result = invoke_agent(
            session_id=session_id,
            user_message=body.message,
            reservation_data=body.reservation_data,
        )
    return AgentChatResponse(
        session_id=session_id,
        final_response=result.get("final_response", ""),
        intent=result.get("intent"),
        reservation_data=result.get("reservation_data"),
    )


# ─── Floor Plan ───────────────────────────────────────────────────────────────


@router.get(
    "/floor-plan",
    summary="Get current floor plan layout",
    tags=["Floor Plan"],
)
async def get_floor_plan() -> dict:
    return floor_plan_service.get_floor_plan()


@router.put(
    "/floor-plan",
    summary="Save floor plan layout (requires can_edit_floor_plan permission)",
    tags=["Floor Plan"],
)
async def save_floor_plan(
    body: dict,
    user: UserInfo = Depends(get_current_user),
) -> dict:
    if not user.can_edit_floor_plan and user.role != "admin":
        raise HTTPException(status_code=403, detail="Floor plan edit permission required")
    floor_plan_service.save_floor_plan(body)
    return {"message": "Floor plan saved", "tables": len(body.get("tables", []))}


@router.get(
    "/floor-plan/assignments",
    summary="Get table assignments for a specific date and hour",
    tags=["Floor Plan"],
)
async def get_assignments(
    date: str = Query(..., description="YYYY-MM-DD"),
    hour: Optional[str] = Query(default=None, description="HH:MM (omit for all hours)"),
) -> AssignmentsForHour:
    rows = floor_plan_service.get_assignments(date, hour)
    return AssignmentsForHour(
        date=date,
        hour=hour or "all",
        assignments=[TableAssignmentResponse(**r) for r in rows],
    )


@router.get(
    "/floor-plan/availability",
    summary="Check available tables for a date, hour, and optional section preference",
    tags=["Floor Plan"],
)
async def check_availability(
    date: str = Query(..., description="YYYY-MM-DD"),
    hour: str = Query(..., description="HH:MM"),
    party_size: int = Query(default=2, ge=1),
    section: Optional[str] = Query(
        default=None, description="Preferred section (e.g. Patio, Window)"
    ),
) -> dict:
    """Returns available tables for a given date/hour, optionally filtered by section and party size."""
    plan = floor_plan_service.get_floor_plan()
    all_tables = plan.get("tables", [])
    assignments = floor_plan_service.get_assignments(date, hour)
    used_ids = {a["table_id"] for a in assignments}
    available = [
        t for t in all_tables if t["id"] not in used_ids and t.get("seats", 0) >= party_size
    ]
    if section:
        s = section.lower()
        matching = [t for t in available if s in (t.get("section", "") or "").lower()]
        return {
            "date": date,
            "hour": hour,
            "party_size": party_size,
            "section": section,
            "matching_tables": [
                {
                    "id": t["id"],
                    "label": t.get("label"),
                    "seats": t.get("seats"),
                    "section": t.get("section"),
                }
                for t in matching
            ],
            "other_available": [
                {
                    "id": t["id"],
                    "label": t.get("label"),
                    "seats": t.get("seats"),
                    "section": t.get("section"),
                }
                for t in available
                if t not in matching
            ],
        }
    return {
        "date": date,
        "hour": hour,
        "party_size": party_size,
        "available_tables": [
            {
                "id": t["id"],
                "label": t.get("label"),
                "seats": t.get("seats"),
                "section": t.get("section"),
            }
            for t in available
        ],
    }


@router.post(
    "/floor-plan/assignments",
    summary="Assign a table to a reservation",
    tags=["Floor Plan"],
)
async def assign_table(
    body: AssignTableRequest,
    user: UserInfo = Depends(get_current_user),
) -> dict:
    if user.role not in ("admin", "writer"):
        raise HTTPException(status_code=403, detail="Writer or admin role required")
    row = floor_plan_service.assign_table(body.table_id, body.reservation_id, body.date, body.hour)
    return {"message": "Table assigned", "assignment": row}


@router.delete(
    "/floor-plan/assignments/{reservation_id}",
    summary="Unassign a table from a reservation",
    tags=["Floor Plan"],
)
async def unassign_table(
    reservation_id: str,
    date: str = Query(...),
    hour: str = Query(...),
    user: UserInfo = Depends(get_current_user),
) -> dict:
    if user.role not in ("admin", "writer"):
        raise HTTPException(status_code=403, detail="Writer or admin role required")
    deleted = floor_plan_service.unassign_table(reservation_id, date, hour)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return {"message": "Assignment removed"}
