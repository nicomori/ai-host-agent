# ai-host-agent — Architecture

## Overview

ai-host-agent is a production-grade voice reservation agent built on the following technology stack:

- **Runtime**: Python 3.11, FastAPI, Uvicorn
- **Agent framework**: LangGraph (stateful multi-agent graph)
- **LLM**: Anthropic Claude (claude-sonnet-4-6 / claude-haiku-4-5)
- **Voice**: OpenAI Whisper (STT) + ElevenLabs (TTS)
- **Telephony**: Twilio
- **Persistence**: PostgreSQL + Redis + LanceDB
- **Containerisation**: Docker (multi-stage) + Docker Compose
- **CI/CD**: GitHub Actions → ghcr.io

---

## Component Diagram

```
[Twilio Webhook] → FastAPI → Guardrails → Supervisor Agent
                                              ↓
                          ┌───────────────────────────────────┐
                          │         LangGraph Graph           │
                          │  ┌──────────┐ ┌───────────────┐  │
                          │  │Reservation│ │Cancellation   │  │
                          │  │  Agent   │ │    Agent      │  │
                          │  └──────────┘ └───────────────┘  │
                          │  ┌──────────┐ ┌───────────────┐  │
                          │  │  Query   │ │   Clarify     │  │
                          │  │  Agent   │ │    Agent      │  │
                          │  └──────────┘ └───────────────┘  │
                          └───────────────────────────────────┘
                                              ↓
                          ┌───────────────────────────────────┐
                          │         Services Layer            │
                          │  ReservationService               │
                          │  VoiceService (STT/TTS)           │
                          │  ConfirmationCallService          │
                          │  SemanticCache (LanceDB)          │
                          └───────────────────────────────────┘
                                              ↓
                          ┌───────────────────────────────────┐
                          │         Persistence               │
                          │  PostgreSQL: reservations,        │
                          │             checkpoints           │
                          │  Redis: session cache             │
                          │  LanceDB: vectors, memory         │
                          └───────────────────────────────────┘
```

---

## Multi-Agent Design

### Supervisor

The supervisor is a LangGraph node that classifies user intent into one of four routing targets:
- `reservation_agent` — book a table
- `cancellation_agent` — cancel a booking
- `query_agent` — check status
- `clarify_agent` — unknown intent

### Sub-agents

Each sub-agent operates independently with its own prompt and tool set. Sub-agents return structured responses that the supervisor composes into a final voice reply.

### State

The `AgentState` TypedDict flows through all nodes:

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]
    session_id: str
    intent: str | None
    reservation: dict | None
    response: str | None
    trace: list[str]
```

---

## Guardrails Pipeline

```
User Input
    │
    ▼
detect_injection()     ← regex: "ignore instructions", "DAN mode", etc.
    │
    ▼
sanitize_input()       ← strip <system>, [INST], ### markers
    │
    ▼
check_length()         ← max 2000 chars
    │
    ▼
mask_pii()             ← phone, email, credit card → [REDACTED]
    │
    ▼
Agent Processing
    │
    ▼
validate_output()      ← no injection echo in response
    │
    ▼
mask_pii(response)     ← second PII pass on output
    │
    ▼
User Response
```

---

## Semantic Cache

LanceDB stores embeddings of past queries. On each new request:
1. Embed the incoming message (768-dim cosine space)
2. ANN search — if cosine similarity ≥ threshold (default 0.92): return cached response
3. On miss: call LLM, store result in cache

Cache stats track hit rate, tokens saved, and estimated cost savings.

---

## Context Window Management

Three strategies for long conversations:

| Strategy | When to use | How it works |
|----------|-------------|--------------|
| `sliding_window` | Simple truncation | Drop oldest messages beyond budget |
| `summarize` | Preserve meaning | Call LLM to summarise old messages |
| `semantic` | Relevance-based | Keep top-N most relevant messages via ANN |

---

## CI/CD Pipeline

```
Push to main/step/**
      │
      ▼
[lint job]
  ruff check + ruff format --check
      │ needs: lint
      ▼
[test job]
  pytest tests/unit/ --cov=src
  artifact: coverage.xml
      │ needs: test
      ▼
[docker-build job]
  docker build (push: false)
      │
      ▼ (only on push to main / tag v*.*.*)
[CD: build-and-push]
  docker/metadata-action → semver + sha tags
  docker/build-push-action → ghcr.io
      │ needs: build-and-push
      ▼
[deploy]
  appleboy/ssh-action → docker compose pull + up
```

---

## Data Models

```python
class Reservation(BaseModel):
    id: str
    guest_name: str
    party_size: int          # 1–20
    date: str                # YYYY-MM-DD
    time: str                # HH:MM
    status: str              # pending | confirmed | cancelled
    notes: str | None

class AgentState(TypedDict):
    messages: list[BaseMessage]
    session_id: str
    intent: str | None
    reservation: dict | None
    response: str | None
    trace: list[str]
```

---

## Deployment

Single-command deploy via Docker Compose:

```bash
docker compose up -d --build
```

Services:
- `api` — FastAPI on port 8000
- `postgres` — PostgreSQL 16 on port 5432
- `redis` — Redis 7 on port 6379

All data persisted via named Docker volumes.
