"""
Step 13 — API layer + UI: Test Suite (ai-host-agent)

7 test cases covering:
  TC-01: Protected endpoint with no API key → 401
  TC-02: Protected endpoint with wrong API key → 401
  TC-03: Protected endpoint with valid API key → 201
  TC-04: Health endpoint does NOT require API key → 200
  TC-05: SSE /reservations/stream returns text/event-stream content-type
  TC-06: SSE stream with ?once=true emits snapshot event with expected fields
  TC-07: OpenAPI spec (/openapi.json) documents all key routes

Error resolutions applied:
  Form 1: APIKeyHeader + Security dependency (auth.py)
  Form 2: once=true param avoids infinite SSE loop in TestClient
  Form 3: scope="module" client fixture avoids repeated app init per test
  Form 4: lru_cache clear + env override for LANCEDB_URI (inherited from test_api.py)
  Form 5: parse SSE bytes directly — no iter_lines() hangup
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

VALID_KEY = "test-step13-host-key"
WRONG_KEY = "wrong-key-xyz"


@pytest.fixture(scope="module")
def client():
    """TestClient with API_KEY set to a known value."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LANCEDB_URI"] = tmp
        os.environ["API_KEY"] = VALID_KEY
        from src.config import get_settings
        get_settings.cache_clear()
        from src.main import create_app
        app = create_app()
        from src.api import routes as _r
        _r.reset_routes()  # Form 1: use reset_routes() instead of direct dict access
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
        get_settings.cache_clear()
        os.environ.pop("LANCEDB_URI", None)
        os.environ.pop("API_KEY", None)


# ─── TC-01: No API key → 401 ─────────────────────────────────────────────────

def test_tc01_no_api_key_returns_401(client: TestClient):
    """TC-01: POST /reservations without X-API-Key must return 401."""
    payload = {
        "guest_name": "Test Guest",
        "guest_phone": "+541199990000",
        "date": "2026-06-01",
        "time": "20:00",
        "party_size": 2,
    }
    r = client.post("/api/v1/reservations", json=payload)
    print(f"\nTC-01 no-key status: {r.status_code}")
    assert r.status_code == 401
    assert "detail" in r.json()


# ─── TC-02: Wrong API key → 401 ──────────────────────────────────────────────

def test_tc02_wrong_api_key_returns_401(client: TestClient):
    """TC-02: POST /reservations with wrong X-API-Key must return 401."""
    payload = {
        "guest_name": "Test Guest",
        "guest_phone": "+541199990001",
        "date": "2026-06-02",
        "time": "21:00",
        "party_size": 3,
    }
    r = client.post(
        "/api/v1/reservations",
        json=payload,
        headers={"X-API-Key": WRONG_KEY},
    )
    print(f"\nTC-02 wrong-key status: {r.status_code}")
    assert r.status_code == 401


# ─── TC-03: Valid API key → 201 ──────────────────────────────────────────────

def test_tc03_valid_api_key_creates_reservation(client: TestClient):
    """TC-03: POST /reservations with valid X-API-Key must return 201."""
    payload = {
        "guest_name": "Step 13 Guest",
        "guest_phone": "+541155550013",
        "date": "2026-07-01",
        "time": "19:30",
        "party_size": 4,
        "notes": "Step 13 test",
    }
    r = client.post(
        "/api/v1/reservations",
        json=payload,
        headers={"X-API-Key": VALID_KEY},
    )
    print(f"\nTC-03 valid-key status: {r.status_code} — {r.json()}")
    assert r.status_code == 201
    data = r.json()
    assert "reservation_id" in data
    assert data["status"] == "confirmed"


# ─── TC-04: Health does NOT require API key ───────────────────────────────────

def test_tc04_health_no_auth_required(client: TestClient):
    """TC-04: GET /health must return 200 without any API key."""
    r = client.get("/health")
    print(f"\nTC-04 health status: {r.status_code}")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── TC-05: SSE endpoint content-type ────────────────────────────────────────

def test_tc05_sse_content_type(client: TestClient):
    """TC-05: GET /reservations/stream must return text/event-stream content-type."""
    with client.stream("GET", "/api/v1/reservations/stream?once=true") as r:
        print(f"\nTC-05 SSE status: {r.status_code} content-type: {r.headers.get('content-type')}")
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")


# ─── TC-06: SSE stream emits snapshot event ───────────────────────────────────

def test_tc06_sse_snapshot_event_fields(client: TestClient):
    """TC-06: SSE ?once=true must emit a data: event with snapshot fields.
    Form 4: accumulate all chunks before parsing to handle large payloads."""
    raw_chunks: list[bytes] = []
    with client.stream("GET", "/api/v1/reservations/stream?once=true") as r:
        assert r.status_code == 200
        for chunk in r.iter_bytes(chunk_size=65536):  # larger chunk size
            raw_chunks.append(chunk)

    raw = b"".join(raw_chunks).decode("utf-8")
    print(f"\nTC-06 SSE raw (first 200): {raw[:200]}")
    assert raw.startswith("data: ")
    # Parse the JSON payload after "data: " up to first double-newline
    json_str = raw.split("data: ", 1)[1].split("\n\n")[0].strip()
    payload = json.loads(json_str)
    assert "event" in payload
    assert payload["event"] == "snapshot"
    assert "reservations" in payload
    assert "total" in payload
    assert "timestamp" in payload


# ─── TC-07: OpenAPI spec documents all key routes ─────────────────────────────

def test_tc07_openapi_spec_documents_routes(client: TestClient):
    """TC-07: GET /openapi.json must include all major route prefixes."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec.get("paths", {})
    print(f"\nTC-07 openapi paths: {list(paths.keys())}")
    # Key routes that must be present
    assert any("/reservations" in p for p in paths), "Missing /reservations route"
    assert any("/voice" in p for p in paths), "Missing /voice route"
    assert any("/agent" in p for p in paths), "Missing /agent route"
    assert any("stream" in p for p in paths), "Missing /stream route (SSE)"


# ─── TC-08: POST /reservations without key → 401 ─────────────────────────────

def test_tc08_post_reservations_no_key_returns_401(client: TestClient):
    """TC-08: POST /api/v1/reservations without X-API-Key must return 401."""
    payload = {
        "guest_name": "Auth Test",
        "guest_phone": "+5491155550001",
        "date": "2026-06-01",
        "time": "19:00",
        "party_size": 2,
    }
    r = client.post("/api/v1/reservations", json=payload)
    print(f"\nTC-08 POST /reservations no-key: {r.status_code}")
    assert r.status_code == 401


# ─── TC-09: GET /reservations with valid key → 200 + list ───────────────────

def test_tc09_get_reservations_with_valid_key(client: TestClient):
    """TC-09: GET /api/v1/reservations with valid key must return 200 and a list."""
    r = client.get("/api/v1/reservations", headers={"X-API-Key": VALID_KEY})
    print(f"\nTC-09 GET /reservations status: {r.status_code} — {r.json()}")
    assert r.status_code == 200
    data = r.json()
    assert "reservations" in data or isinstance(data, list), \
        "Response must contain reservations list"


# ─── TC-10: POST /reservations empty name → 422 ──────────────────────────────

def test_tc10_post_reservation_empty_name_422(client: TestClient):
    """TC-10: POST /reservations with empty guest_name must return 422."""
    payload = {
        "guest_name": "",
        "guest_phone": "+541100000099",
        "date": "2026-08-01",
        "time": "20:00",
        "party_size": 2,
    }
    r = client.post(
        "/api/v1/reservations",
        json=payload,
        headers={"X-API-Key": VALID_KEY},
    )
    print(f"\nTC-10 empty name status: {r.status_code}")
    assert r.status_code == 422


# ─── TC-11: POST /voice/inbound with valid key → 200 ─────────────────────────

def test_tc11_voice_inbound_returns_200(client: TestClient):
    """TC-11: POST /api/v1/voice/inbound with Twilio form-encoded payload must return 200."""
    payload = {
        "CallSid": "CA-step13-tc11",
        "From": "+541199990011",
        "To": "+541100000001",
        "CallStatus": "ringing",
    }
    r = client.post(
        "/api/v1/voice/inbound",
        data=payload,
    )
    print(f"\nTC-11 voice/inbound status: {r.status_code}")
    assert r.status_code == 200


# ─── TC-12: GET /health has restaurant_name field ────────────────────────────

def test_tc12_health_has_restaurant_name(client: TestClient):
    """TC-12: GET /health response must include a restaurant field."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    print(f"\nTC-12 health body: {body}")
    # field is 'restaurant' (not 'restaurant_name')
    assert "restaurant" in body, f"health must have restaurant. Got: {list(body.keys())}"
    assert isinstance(body["restaurant"], str) and len(body["restaurant"]) > 0


# ─── TC-13: GET /openapi.json has info.title ─────────────────────────────────

def test_tc13_openapi_has_info_title(client: TestClient):
    """TC-13: GET /openapi.json must have a non-empty info.title."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    title = spec.get("info", {}).get("title", "")
    print(f"\nTC-13 openapi title: {title!r}")
    assert title.strip(), "openapi.json info.title must be non-empty"


# ─── TC-14: Two reservations → GET /reservations total correct ───────────────

def test_tc14_two_reservations_total_matches(client: TestClient):
    """TC-14: Creating two reservations must increment the list total by 2."""
    from src.api import routes as _r
    _r.reset_routes()  # Form 3: DB truncate for clean state in test

    for i, phone in enumerate(["+541155550141", "+541155550142"], start=1):
        client.post(
            "/api/v1/reservations",
            json={
                "guest_name": f"TC14 Guest {i}",
                "guest_phone": phone,
                "date": "2026-09-01",
                "time": "19:00",
                "party_size": 2,
            },
            headers={"X-API-Key": VALID_KEY},
        )

    r = client.get("/api/v1/reservations", headers={"X-API-Key": VALID_KEY})
    assert r.status_code == 200
    data = r.json()
    total = data.get("total", len(data)) if isinstance(data, dict) else len(data)
    print(f"\nTC-14 total after 2 creates: {total}")
    assert total >= 2, f"Expected ≥ 2 reservations, got {total}"


# ─── TC-15: POST /agent/chat with valid key → 200 + session_id ───────────────

def test_tc15_agent_chat_returns_session_id(client: TestClient):
    """TC-15: POST /api/v1/agent/chat must return 200 and a non-empty session_id."""
    payload = {"message": "Hi, can you help me make a reservation?"}
    r = client.post(
        "/api/v1/agent/chat",
        json=payload,
        headers={"X-API-Key": VALID_KEY},
    )
    print(f"\nTC-15 agent/chat status: {r.status_code} — {r.json()}")
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data, "agent/chat response must include session_id"
    assert data["session_id"], "session_id must be non-empty"
