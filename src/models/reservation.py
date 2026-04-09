"""Pydantic models for HostAI — Reservations + Voice."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ReservationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    SEATED = "seated"
    NO_SHOW = "no_show"


class ConfirmationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    NO_ANSWER = "no_answer"
    FAILED = "failed"


class CallStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"


# ─── Request models ────────────────────────────────────────────────────────────


class CreateReservationRequest(BaseModel):
    guest_name: str = Field(..., min_length=2, max_length=100)
    guest_phone: str = Field(..., min_length=7, max_length=20)
    date: str = Field(..., description="ISO date: YYYY-MM-DD")
    time: str = Field(..., description="HH:MM (24h)")
    party_size: int = Field(..., ge=1, le=20)
    preference: Optional[str] = Field(default=None, max_length=50)
    special_requests: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD format")
        return v

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("time must be HH:MM format")
        return v


class CancelReservationRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=300)


class VoiceInboundRequest(BaseModel):
    call_sid: str = Field(..., description="Twilio CallSid")
    from_number: str
    to_number: str
    call_status: str = Field(default="ringing")


# ─── Response models ───────────────────────────────────────────────────────────


class ReservationResponse(BaseModel):
    reservation_id: str
    guest_name: str
    guest_phone: str
    date: str
    time: str
    party_size: int
    status: ReservationStatus
    preference: Optional[str] = None
    special_requests: Optional[str] = None
    notes: Optional[str] = None
    confirmation_status: str = "pending"
    confirmation_called_at: Optional[str] = None
    created_at: str
    updated_at: str


class ReservationListResponse(BaseModel):
    reservations: list[ReservationResponse]
    total: int
    page: int = 1
    page_size: int = 20


class CreateReservationResponse(BaseModel):
    reservation_id: str
    status: ReservationStatus
    message: str
    confirmation_call_scheduled_at: Optional[str] = None


class CancelReservationResponse(BaseModel):
    reservation_id: str
    status: ReservationStatus
    message: str


class VoiceInboundResponse(BaseModel):
    call_sid: str
    session_id: str
    status: str
    message: str


class VoiceOutboundResponse(BaseModel):
    reservation_id: str
    call_sid: Optional[str] = None
    status: CallStatus
    message: str


class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    restaurant: str
    version: str
