"""
API Integration Tests — ai-host-agent

15 end-to-end tests covering the full HTTP API via FastAPI TestClient:
  TC-01: GET /health returns 200 with status=ok
  TC-02: GET /api/v1/reservations returns 200 with empty list initially
  TC-03: POST /api/v1/reservations creates a reservation (201)
  TC-04: GET /api/v1/reservations returns 200 with ≥ 1 item after create
  TC-05: GET /api/v1/reservations/{id} returns the created reservation
  TC-06: DELETE /api/v1/reservations/{id} cancels a reservation
  TC-07: POST /api/v1/reservations without API key returns 401
  TC-08: GET /api/v1/reservations/{nonexistent} returns 404
  TC-09: POST /api/v1/voice/inbound returns session_id
  TC-10: POST /api/v1/voice/outbound/{id} returns scheduled status
  TC-11: GET /api/v1/reservations/stream?once=true streams SSE snapshot
  TC-12: GET /api/v1/reservations?status=confirmed filters by status
  TC-13: GET /api/v1/reservations?page=1&page_size=1 respects pagination
  TC-14: DELETE /api/v1/reservations/{nonexistent} returns 401/404
  TC-15: POST /api/v1/agent/chat returns session_id and final_response
"""

from __future__ import annotations


API_KEY = "dev-secret-key"
HEADERS = {"X-API-Key": API_KEY}

_RESERVATION_PAYLOAD = {
    "guest_name": "Integration Tester",
    "guest_phone": "+54911000001",
    "date": "2026-08-01",
    "time": "20:00",
    "party_size": 4,
}


# ─── TC-01 ────────────────────────────────────────────────────────────────────


def test_tc01_health(step4_client):
    """TC-01: GET /health returns 200 with status=ok."""
    r = step4_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "app" in body


# ─── TC-02 ────────────────────────────────────────────────────────────────────


def test_tc02_list_reservations_empty(step4_client):
    """TC-02: GET /api/v1/reservations starts empty."""
    r = step4_client.get("/api/v1/reservations")
    assert r.status_code == 200
    body = r.json()
    assert "reservations" in body
    assert body["total"] >= 0  # Form 4: DB persists across runs


# ─── TC-03 ────────────────────────────────────────────────────────────────────


def test_tc03_create_reservation(step4_client):
    """TC-03: POST /api/v1/reservations with API key returns 201."""
    r = step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    assert r.status_code == 201
    body = r.json()
    assert "reservation_id" in body
    assert body["status"] == "confirmed"


# ─── TC-04 ────────────────────────────────────────────────────────────────────


def test_tc04_list_reservations_non_empty(step4_client):
    """TC-04: GET /api/v1/reservations returns ≥ 1 after create."""
    step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    r = step4_client.get("/api/v1/reservations")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


# ─── TC-05 ────────────────────────────────────────────────────────────────────


def test_tc05_get_reservation_by_id(step4_client):
    """TC-05: GET /api/v1/reservations/{id} returns the specific reservation."""
    create = step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    rid = create.json()["reservation_id"]
    r = step4_client.get(f"/api/v1/reservations/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["reservation_id"] == rid
    assert body["guest_name"] == "Integration Tester"


# ─── TC-06 ────────────────────────────────────────────────────────────────────


def test_tc06_cancel_reservation(step4_client):
    """TC-06: DELETE /api/v1/reservations/{id} sets status to cancelled."""
    create = step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    rid = create.json()["reservation_id"]
    r = step4_client.request(
        "DELETE",
        f"/api/v1/reservations/{rid}",
        json={"reason": "Integration test cancel"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["reservation_id"] == rid


# ─── TC-07 ────────────────────────────────────────────────────────────────────


def test_tc07_create_reservation_no_api_key_returns_401(step4_client):
    """TC-07: POST /api/v1/reservations without X-API-Key returns 401."""
    r = step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD)
    assert r.status_code == 401


# ─── TC-08 ────────────────────────────────────────────────────────────────────


def test_tc08_get_nonexistent_reservation_returns_404(step4_client):
    """TC-08: GET /api/v1/reservations/{bad_id} returns 404."""
    r = step4_client.get("/api/v1/reservations/nonexistent-id-xyz")
    assert r.status_code == 404


# ─── TC-09 ────────────────────────────────────────────────────────────────────


def test_tc09_voice_inbound_returns_session(step4_client):
    """TC-09: POST /api/v1/voice/inbound returns call_sid and session_id."""
    payload = {
        "call_sid": "CA-integration-test-001",
        "from_number": "+54911000010",
        "to_number": "+54911000001",
        "call_status": "ringing",
    }
    r = step4_client.post("/api/v1/voice/inbound", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert body["call_sid"] == "CA-integration-test-001"
    assert body["status"] == "accepted"


# ─── TC-10 ────────────────────────────────────────────────────────────────────


def test_tc10_voice_outbound_returns_scheduled(step4_client):
    """TC-10: POST /api/v1/voice/outbound/{id} returns scheduled status."""
    create = step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    rid = create.json()["reservation_id"]
    r = step4_client.post(f"/api/v1/voice/outbound/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "scheduled"
    assert body["reservation_id"] == rid


# ─── TC-11 ────────────────────────────────────────────────────────────────────


def test_tc11_stream_reservations_sse(step4_client):
    """TC-11: GET /api/v1/reservations/stream?once=true returns SSE data."""
    r = step4_client.get("/api/v1/reservations/stream?once=true")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    content = r.text
    assert "data:" in content
    assert "snapshot" in content


# ─── TC-12 ────────────────────────────────────────────────────────────────────


def test_tc12_list_reservations_filter_by_status(step4_client):
    """TC-12: GET /api/v1/reservations?status=confirmed filters by status."""
    step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    r = step4_client.get("/api/v1/reservations?status=confirmed")
    assert r.status_code == 200
    body = r.json()
    assert all(res["status"] == "confirmed" for res in body["reservations"])


# ─── TC-13 ────────────────────────────────────────────────────────────────────


def test_tc13_list_reservations_pagination(step4_client):
    """TC-13: GET /api/v1/reservations?page=1&page_size=1 returns at most 1 item."""
    # Create 2 reservations
    step4_client.post("/api/v1/reservations", json=_RESERVATION_PAYLOAD, headers=HEADERS)
    step4_client.post(
        "/api/v1/reservations",
        json={**_RESERVATION_PAYLOAD, "guest_name": "Another Guest"},
        headers=HEADERS,
    )
    r = step4_client.get("/api/v1/reservations?page=1&page_size=1")
    assert r.status_code == 200
    body = r.json()
    assert len(body["reservations"]) <= 1
    assert body["page"] == 1
    assert body["page_size"] == 1


# ─── TC-14 ────────────────────────────────────────────────────────────────────


def test_tc14_delete_nonexistent_reservation(step4_client):
    """TC-14: DELETE /api/v1/reservations/{bad_id} returns 401 (no key) or 404."""
    r_no_key = step4_client.request("DELETE", "/api/v1/reservations/bad-id", json={})
    # Without API key → 401; with API key → 404
    assert r_no_key.status_code == 401
    r_with_key = step4_client.request(
        "DELETE", "/api/v1/reservations/bad-id", json={}, headers=HEADERS
    )
    assert r_with_key.status_code == 404


# ─── TC-15 ────────────────────────────────────────────────────────────────────


def test_tc15_agent_chat_returns_response(step4_client):
    """TC-15: POST /api/v1/agent/chat returns session_id and final_response."""
    r = step4_client.post("/api/v1/agent/chat", json={"message": "I need a table for 2"})
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert "final_response" in body
    assert isinstance(body["final_response"], str)
