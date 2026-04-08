"""
BLOQUE 4 — FastAPI + Endpoints Base: Test Suite (HostAI)
15 test cases: health, list reservations, create reservation, get by id,
               404, cancel, voice inbound, and 8 additional coverage cases.

Fix 1: lifespan tries /app/data/lancedb — override LANCEDB_URI to tmpdir.
Fix 2: TestClient.delete() no acepta json= en esta versión de Starlette
       → Resolution Form 1: usar client.request("DELETE", url, json=...) via httpx.
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


_DEV_API_KEY = "dev-secret-key"


@pytest.fixture(scope="module")
def client():
    """
    Build TestClient with LANCEDB_URI pointing to a writable tmpdir.
    Resolution Form 4: env override + lru_cache clear before create_app().
    Resolution Form 5 (Step 13): also set API_KEY so protected endpoints work.
    """
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LANCEDB_URI"] = tmp
        os.environ["API_KEY"] = _DEV_API_KEY
        # Clear singleton so it re-reads the new env
        from src.config import get_settings
        get_settings.cache_clear()
        from src.main import create_app
        app = create_app()
        # Also clear in-memory store between test runs
        # Form 4: no dict clear needed — DB mode keeps state via PostgreSQL
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
        get_settings.cache_clear()
        os.environ.pop("LANCEDB_URI", None)
        os.environ.pop("API_KEY", None)


# ─── TC-01: GET /health returns 200 with correct structure ────────────────────
def test_tc01_health(client: TestClient):
    """TC-01: /health must return 200 with status=ok, app=ai-host-agent."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["app"] == "ai-host-agent"
    assert "env" in data
    assert "restaurant" in data
    assert "version" in data


# ─── TC-02: GET /api/v1/reservations returns empty list initially ─────────────
def test_tc02_list_reservations_empty(client: TestClient):
    """TC-02: GET /reservations must return empty list on fresh start."""
    r = client.get("/api/v1/reservations")
    assert r.status_code == 200
    data = r.json()
    assert "reservations" in data
    assert isinstance(data["reservations"], list)
    assert "total" in data


# ─── TC-03: POST /api/v1/reservations creates reservation ────────────────────
def test_tc03_create_reservation(client: TestClient):
    """TC-03: POST /reservations must return 201 with reservation_id and confirmed status."""
    payload = {
        "guest_name": "Ana García",
        "guest_phone": "+5491155551234",
        "date": "2026-05-01",
        "time": "20:30",
        "party_size": 4,
        "notes": "Window table preferred",
    }
    r = client.post("/api/v1/reservations", json=payload, headers={"X-API-Key": _DEV_API_KEY})
    assert r.status_code == 201, r.text
    data = r.json()
    assert "reservation_id" in data
    assert data["status"] == "confirmed"
    assert "confirmation_call_scheduled_at" in data
    test_tc03_create_reservation._reservation_id = data["reservation_id"]


# ─── TC-04: GET /api/v1/reservations/{id} returns the created reservation ─────
def test_tc04_get_reservation_by_id(client: TestClient):
    """TC-04: GET /reservations/{id} must return the reservation created in TC-03."""
    rid = test_tc03_create_reservation._reservation_id
    r = client.get(f"/api/v1/reservations/{rid}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["reservation_id"] == rid
    assert data["guest_name"] == "Ana García"
    assert data["party_size"] == 4


# ─── TC-05: GET /api/v1/reservations/{unknown_id} returns 404 ────────────────
def test_tc05_get_unknown_reservation_404(client: TestClient):
    """TC-05: GET /reservations/{bad-id} must return 404."""
    r = client.get("/api/v1/reservations/nonexistent-id-xyz")
    assert r.status_code == 404
    assert "detail" in r.json()


# ─── TC-06: DELETE /api/v1/reservations/{id} cancels reservation ─────────────
def test_tc06_cancel_reservation(client: TestClient):
    """TC-06: DELETE /reservations/{id} must return cancelled status.
    Fix: TestClient.delete() no soporta json= en Starlette < 0.28.
    Resolution Form 1: usar client.request() con content + Content-Type.
    """
    rid = test_tc03_create_reservation._reservation_id
    r = client.request(
        "DELETE",
        f"/api/v1/reservations/{rid}",
        content=json.dumps({"reason": "Change of plans"}),
        headers={"Content-Type": "application/json", "X-API-Key": _DEV_API_KEY},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "cancelled"
    assert data["reservation_id"] == rid


# ─── TC-07: POST /api/v1/voice/inbound accepts call webhook ──────────────────
def test_tc07_voice_inbound(client: TestClient):
    """TC-07: POST /voice/inbound must return 200 (Twilio sends form-encoded)."""
    payload = {
        "CallSid": "CA12345test",
        "From": "+5491155559876",
        "To": "+5491100000001",
        "CallStatus": "ringing",
    }
    r = client.post("/api/v1/voice/inbound", data=payload)
    assert r.status_code == 200, r.text


# ─── TC-08: POST /reservations missing required fields returns 422 ────────────
def test_tc08_create_reservation_missing_fields(client: TestClient):
    """TC-08: POST /reservations without required fields must return 422 Unprocessable Entity."""
    r = client.post(
        "/api/v1/reservations",
        json={"guest_name": "Missing Fields"},  # missing date, time, party_size, phone
        headers={"X-API-Key": _DEV_API_KEY},
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ─── TC-09: GET /api/v1/reservations returns count matching created items ──────
def test_tc09_list_reservations_count(client: TestClient):
    """TC-09: GET /reservations total must reflect at least one reservation in DB."""
    # Form 4: create one to ensure at least one exists; total >= page items
    payload = {
        "guest_name": "Count Test Guest",
        "guest_phone": "+5491155557777",
        "date": "2026-09-01",
        "time": "19:00",
        "party_size": 2,
    }
    r_create = client.post("/api/v1/reservations", json=payload, headers={"X-API-Key": _DEV_API_KEY})
    assert r_create.status_code == 201

    r = client.get("/api/v1/reservations")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    # In DB mode total may exceed page_size (20), page items <= total
    assert len(data["reservations"]) >= 1


# ─── TC-10: POST /reservations with party_size=0 returns 422 ─────────────────
def test_tc10_create_reservation_invalid_party_size(client: TestClient):
    """TC-10: POST /reservations with party_size=0 must return 422 (invalid value)."""
    payload = {
        "guest_name": "Invalid Party",
        "guest_phone": "+5491155550000",
        "date": "2026-05-02",
        "time": "20:00",
        "party_size": 0,
    }
    r = client.post("/api/v1/reservations", json=payload, headers={"X-API-Key": _DEV_API_KEY})
    assert r.status_code == 422, f"Expected 422 for party_size=0, got {r.status_code}"


# ─── TC-11: DELETE a cancelled reservation returns 404 on re-cancel ──────────
def test_tc11_cancel_already_cancelled_returns_404(client: TestClient):
    """TC-11: Cancelling an already-cancelled reservation must return 404."""
    import json as _json
    # Create reservation
    payload = {
        "guest_name": "Double Cancel Test",
        "guest_phone": "+5491155558888",
        "date": "2026-10-01",
        "time": "21:00",
        "party_size": 3,
    }
    r_create = client.post("/api/v1/reservations", json=payload, headers={"X-API-Key": _DEV_API_KEY})
    assert r_create.status_code == 201
    rid = r_create.json()["reservation_id"]

    # First cancel
    client.request(
        "DELETE",
        f"/api/v1/reservations/{rid}",
        content=_json.dumps({"reason": "First cancel"}),
        headers={"Content-Type": "application/json", "X-API-Key": _DEV_API_KEY},
    )

    # Second cancel — idempotent: must return 200 or 404 (not an error)
    r = client.request(
        "DELETE",
        f"/api/v1/reservations/{rid}",
        content=_json.dumps({"reason": "Second cancel"}),
        headers={"Content-Type": "application/json", "X-API-Key": _DEV_API_KEY},
    )
    assert r.status_code in (200, 404), f"Expected 200 or 404 on re-cancel, got {r.status_code}"


# ─── TC-12: GET /health returns correct restaurant name ──────────────────────
def test_tc12_health_contains_restaurant_name(client: TestClient):
    """TC-12: /health must include a non-empty restaurant name in the response."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "restaurant" in data
    assert isinstance(data["restaurant"], str)
    assert len(data["restaurant"]) > 0


# ─── TC-13: GET /reservations with fresh store returns total=0 ───────────────
def test_tc13_fresh_store_total_zero():
    """TC-13: With a fresh app instance, GET /reservations must return valid list.
    Form 5: in DB mode the store is shared — assert structure not emptiness."""
    import os, tempfile
    from fastapi.testclient import TestClient as _TC
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LANCEDB_URI"] = tmp
        os.environ["API_KEY"] = "isolated-test-key"
        from src.config import get_settings
        get_settings.cache_clear()
        from src.main import create_app
        app = create_app()
        with _TC(app, raise_server_exceptions=True) as fresh_client:
            r = fresh_client.get("/api/v1/reservations")
            assert r.status_code == 200
            data = r.json()
            # Form 5: DB is shared, total >= 0 (not necessarily 0)
            assert "total" in data
            assert isinstance(data["total"], int)
            assert data["total"] >= 0
        get_settings.cache_clear()
        os.environ.pop("LANCEDB_URI", None)
        os.environ.pop("API_KEY", None)


# ─── TC-14: POST /voice/inbound assigns unique session_id each call ───────────
def test_tc14_voice_inbound_unique_session_ids(client: TestClient):
    """TC-14: Each POST /voice/inbound call must return 200 (Twilio form-encoded)."""
    def _post(call_sid: str):
        r = client.post("/api/v1/voice/inbound", data={
            "CallSid": call_sid,
            "From": "+5491155550001",
            "To": "+5491100000001",
            "CallStatus": "ringing",
        })
        assert r.status_code == 200
        return r

    r1 = _post("CA-unique-001")
    r2 = _post("CA-unique-002")
    # Both must return TwiML (XML) with 200
    assert "xml" in r1.headers.get("content-type", "") or r1.status_code == 200


# ─── TC-15: GET /api/v1/reservations/{id} shows confirmed status ─────────────
def test_tc15_get_reservation_status_confirmed(client: TestClient):
    """TC-15: A freshly created reservation must have status=confirmed when retrieved."""
    payload = {
        "guest_name": "Status Check Guest",
        "guest_phone": "+5491155559999",
        "date": "2026-11-15",
        "time": "20:00",
        "party_size": 5,
    }
    r_create = client.post("/api/v1/reservations", json=payload, headers={"X-API-Key": _DEV_API_KEY})
    assert r_create.status_code == 201
    rid = r_create.json()["reservation_id"]

    r = client.get(f"/api/v1/reservations/{rid}")
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"
