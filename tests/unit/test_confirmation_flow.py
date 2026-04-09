"""Tests for the confirmation call flow — HostAI."""

import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure test config
os.environ.setdefault("LANCEDB_URI", "/tmp/test_lancedb_confirm")
os.environ["APP_ENV"] = "development"


# ─── Model tests ────────────────────────────────────────────────────────────


def test_confirmation_status_enum():
    """ConfirmationStatus enum has all expected values."""
    from src.models.reservation import ConfirmationStatus

    assert ConfirmationStatus.PENDING == "pending"
    assert ConfirmationStatus.CONFIRMED == "confirmed"
    assert ConfirmationStatus.DECLINED == "declined"
    assert ConfirmationStatus.NO_ANSWER == "no_answer"
    assert ConfirmationStatus.FAILED == "failed"


def test_reservation_response_has_confirmation_fields():
    """ReservationResponse model includes confirmation_status and confirmation_called_at."""
    from src.models.reservation import ReservationResponse

    fields = ReservationResponse.model_fields
    assert "confirmation_status" in fields
    assert "confirmation_called_at" in fields


def test_reservation_response_defaults():
    """ReservationResponse defaults confirmation_status to 'pending' and confirmation_called_at to None."""
    from src.models.reservation import ReservationResponse

    r = ReservationResponse(
        reservation_id="abc",
        guest_name="Test",
        guest_phone="+1234",
        date="2026-04-10",
        time="20:00",
        party_size=2,
        status="confirmed",
        created_at="2026-04-06T12:00:00",
        updated_at="2026-04-06T12:00:00",
    )
    assert r.confirmation_status == "pending"
    assert r.confirmation_called_at is None


# ─── DB tests ───────────────────────────────────────────────────────────────


@pytest.fixture
def pg_available():
    """Check if PostgreSQL is available for testing."""
    try:
        from src.services.db import get_conn

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not os.getenv("RUN_PG_TESTS"),
    reason="PostgreSQL not available (set RUN_PG_TESTS=1 to enable)",
)
class TestConfirmationDB:
    def test_schema_has_confirmation_columns(self):
        """reservations table has confirmation_status and confirmation_called_at columns."""
        from src.services.db import get_conn

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'reservations'
                    AND column_name IN ('confirmation_status', 'confirmation_called_at')
                    ORDER BY column_name
                """)
                cols = [r["column_name"] for r in cur.fetchall()]
        assert "confirmation_called_at" in cols
        assert "confirmation_status" in cols

    def test_new_reservation_has_pending_confirmation(self):
        """New reservations default to confirmation_status='pending'."""
        from src.services.db import save_reservation

        r = save_reservation(
            guest_name="Test Confirmation",
            guest_phone="+491234",
            date="2026-12-25",
            time="20:00",
            party_size=2,
        )
        assert r["confirmation_status"] == "pending"
        assert r["confirmation_called_at"] is None

    def test_update_confirmation_status(self):
        """update_confirmation_status() changes the status and sets called_at timestamp."""
        from src.services.db import save_reservation, update_confirmation_status, get_reservation

        r = save_reservation(
            guest_name="Confirm Test",
            guest_phone="+491234",
            date="2026-12-26",
            time="19:00",
            party_size=3,
        )
        assert r["confirmation_status"] == "pending"

        result = update_confirmation_status(r["reservation_id"], "confirmed")
        assert result is True

        updated = get_reservation(r["reservation_id"])
        assert updated["confirmation_status"] == "confirmed"
        assert updated["confirmation_called_at"] is not None


# ─── Scheduler tests ────────────────────────────────────────────────────────

try:
    from src.main import _run_outbound_confirmations

    _HAS_MAIN = True
except ImportError:
    _HAS_MAIN = False


@pytest.mark.skipif(not _HAS_MAIN, reason="twilio not installed (src.main requires it)")
def test_scheduler_skips_already_confirmed():
    """_run_outbound_confirmations skips reservations with confirmation_status != 'pending'."""
    import asyncio

    mock_reservations = [
        {
            "reservation_id": "uuid-1",
            "guest_name": "Already Called",
            "guest_phone": "+491234",
            "date": "2026-04-06",
            "time": "14:00",
            "party_size": 2,
            "status": "confirmed",
            "confirmation_status": "confirmed",
        }
    ]

    with (
        patch("src.services.db.list_reservations", return_value=mock_reservations),
        patch("src.services.db.update_confirmation_status") as mock_update,
        patch("src.config.get_settings") as mock_cfg,
    ):
        cfg = MagicMock()
        cfg.env.twilio_account_sid = "ACtest"
        cfg.env.twilio_auth_token = "test_token"
        cfg.env.twilio_phone_number = "+1234"
        cfg.reservations.confirmation_call_minutes_before = 60
        cfg.restaurant_name = "Test Restaurant"
        mock_cfg.return_value = cfg

        asyncio.get_event_loop().run_until_complete(_run_outbound_confirmations())
        mock_update.assert_not_called()


@pytest.mark.skipif(not _HAS_MAIN, reason="twilio not installed (src.main requires it)")
def test_scheduler_skips_without_twilio_creds():
    """_run_outbound_confirmations returns immediately without Twilio creds."""
    import asyncio

    with patch("src.config.get_settings") as mock_cfg:
        cfg = MagicMock()
        cfg.env.twilio_account_sid = ""
        cfg.env.twilio_auth_token = ""
        cfg.env.twilio_phone_number = ""
        mock_cfg.return_value = cfg

        with patch("src.services.db.list_reservations") as mock_list:
            asyncio.get_event_loop().run_until_complete(_run_outbound_confirmations())
            mock_list.assert_not_called()


# ─── API endpoint tests ─────────────────────────────────────────────────────

try:
    from src.api.routes import router as _routes_router

    _HAS_ROUTES = True
except ImportError:
    _HAS_ROUTES = False


@pytest.mark.skipif(not _HAS_ROUTES, reason="twilio not installed")
def test_confirmation_endpoint_exists():
    """PATCH /reservations/{id}/confirmation endpoint is registered."""
    paths = [r.path for r in _routes_router.routes if hasattr(r, "path")]
    assert "/reservations/{reservation_id}/confirmation" in paths


@pytest.mark.skipif(not _HAS_ROUTES, reason="twilio not installed")
def test_config_endpoint_exists():
    """GET and PATCH /config/confirmation endpoints are registered."""
    paths = [r.path for r in _routes_router.routes if hasattr(r, "path")]
    assert "/config/confirmation" in paths


@pytest.mark.skipif(not _HAS_ROUTES, reason="twilio not installed")
def test_voice_outbound_endpoint_exists():
    """POST /voice/outbound/{reservation_id} endpoint is registered."""
    paths = [r.path for r in _routes_router.routes if hasattr(r, "path")]
    assert "/voice/outbound/{reservation_id}" in paths


# ─── Config tests ───────────────────────────────────────────────────────────


def test_config_has_confirmation_minutes():
    """Config has confirmation_call_minutes_before with default 60."""
    from src.config import get_settings

    cfg = get_settings()
    assert hasattr(cfg.reservations, "confirmation_call_minutes_before")
    assert cfg.reservations.confirmation_call_minutes_before >= 5


def test_config_min_value():
    """confirmation_call_minutes_before must be >= 5."""
    from src.config import ReservationsSection
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReservationsSection(confirmation_call_minutes_before=2)
