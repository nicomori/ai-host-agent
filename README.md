# HostAI — ai-host-agent

**Agente de reservas por voz para restaurantes** — Claude + LangGraph multi-agente, llamadas telefónicas via Twilio, TTS con ElevenLabs, persistencia en PostgreSQL, dashboard de gestión en React, y streaming SSE en tiempo real.

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Un cliente llama por teléfono al restaurante. El agente atiende en español, entiende la intención (reservar, cancelar, consultar), recopila los datos necesarios de forma conversacional, y persiste la reserva en PostgreSQL. El dashboard web permite ver reservas en tiempo real, gestionar el plano del restaurante, y asignar mesas.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Llamada entrante (Twilio)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ POST /api/v1/voice/inbound
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Gateway                            │
│  /health  /reservations  /voice  /agent/chat  /stream  /floor  │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         Twilio STT    ElevenLabs TTS   LangGraph
         (es-ES)       (turbo v2.5)     Supervisor
                                            │
                    ┌───────────┬────────────┼───────────┐
                    ▼           ▼            ▼           ▼
              Reservation  Cancellation   Query      Clarify
                Agent        Agent       Agent       Agent
                    │
                    ▼
              PostgreSQL ← Redis ← LanceDB (cache semántico)
```

### Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11, FastAPI, Uvicorn |
| Agentes | LangGraph (Supervisor pattern), Claude Haiku 4.5 |
| Voz | Twilio (STT es-ES), ElevenLabs (TTS turbo v2.5) |
| Base de datos | PostgreSQL 16, Redis 7 |
| Cache semántico | LanceDB |
| Frontend | React 18, Vite, TailwindCSS, React Konva, TanStack Query |
| Infraestructura | Docker Compose, Cloudflare Quick Tunnel |
| Observabilidad | Langfuse v4 (trazas `[HostAI] - *`) |

---

## Features

| Feature | Detalle |
|---------|---------|
| **Multi-agente** | Supervisor → Reservation / Cancellation / Query / Clarify |
| **Voz natural** | ElevenLabs turbo v2.5, estilo conversacional rioplatense |
| **Pipeline de voz** | Twilio STT (es-ES) → Claude Haiku → ElevenLabs TTS streaming |
| **Guardrails** | Detección de prompt injection (58 patrones), PII masking, límite de input |
| **Cache semántico** | LanceDB — evita llamadas LLM redundantes |
| **Context window** | Sliding window + summarization + selección semántica |
| **Checkpointing** | LangGraph persiste estado de conversación entre turnos |
| **SSE en tiempo real** | Stream de reservas para actualización live en dashboard |
| **Llamadas salientes** | Confirmación automática de reservas via Twilio (APScheduler) |
| **Dashboard interactivo** | Cards, floor plan (React Konva), timeline por hora, dark mode, i18n |
| **Auth JWT + RBAC** | Roles admin/writer/reader con permisos granulares |
| **ErrorBoundary** | Captura errores de React con UI de recuperación |

---

## Observabilidad

Todas las trazas en Langfuse usan el prefijo **`[HostAI] -`** seguido del step exacto:

| Span | Tipo | Ejemplo |
|------|------|---------|
| Root trace | CHAIN | `[HostAI] - HostAI — Nueva reserva — "Quiero reservar..."` |
| Supervisor | AGENT | `[HostAI] - Clasificador → Nueva reserva → reservation_agent` |
| Sub-agent | AGENT | `[HostAI] - Reserva — Nicolás Mori` |
| Cancelación | AGENT | `[HostAI] - Cancelación — pidiendo ID` |
| Consulta | AGENT | `[HostAI] - Consulta — reserva abc12345` |
| Clarify | AGENT | `[HostAI] - Bienvenida — intent no identificado` |
| DB Init | LOG | `[HostAI] - DB Init: PostgreSQL schema initialized` |

Los logs de aplicación (structlog) también usan el prefijo `[HostAI] -` para correlación.

Para ver las trazas: [Langfuse Cloud](https://cloud.langfuse.com) → filtrar por `[HostAI]`.

---

## Servicios (Docker Compose)

| Servicio | Container | Puerto host | Puerto interno | Imagen |
|----------|-----------|-------------|----------------|--------|
| API | ai-host-agent | 8000 | 8000 | Build local (Python 3.11) |
| PostgreSQL | ai-host-agent-postgres | 5433 | 5432 | postgres:16-alpine |
| Redis | ai-host-agent-redis | 6380 | 6379 | redis:7-alpine |
| Tunnel | ai-host-agent-tunnel | — | — | cloudflare/cloudflared:latest |
| UI (dev) | — (local) | 5173 | — | Node 18+ |

---

## Quickstart

### Prerequisitos

- Docker Desktop instalado y corriendo
- Node.js 18+ (para el dashboard UI)
- Cuentas en: [Anthropic](https://console.anthropic.com), [ElevenLabs](https://elevenlabs.io), [Twilio](https://twilio.com)

### 1. Clonar y configurar credenciales

```bash
git clone https://github.com/NicolasMori/ai-host-agent.git
cd ai-host-agent
cp .env.example .env
```

Editar `.env` con tus credenciales:

```bash
# REQUERIDAS — sin estas no funciona
ANTHROPIC_API_KEY=sk-ant-...          # https://console.anthropic.com → API Keys
API_KEY=tu-api-key-para-gateway       # Cualquier string secreto
JWT_SECRET_KEY=tu-jwt-secret          # Secret para tokens JWT (cambiar del default)

# REQUERIDAS para voz (Twilio + ElevenLabs)
ELEVENLABS_API_KEY=...                # https://elevenlabs.io → Profile → API Key
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL  # ID de voz (Sarah por defecto)
TWILIO_ACCOUNT_SID=AC...              # https://console.twilio.com → Account SID
TWILIO_AUTH_TOKEN=...                 # https://console.twilio.com → Auth Token
TWILIO_PHONE_NUMBER=+1...            # Número comprado en Twilio
TWILIO_WEBHOOK_BASE_URL=https://...   # URL del tunnel (se completa en paso 4)

# OPCIONALES
OPENAI_API_KEY=sk-...                 # Para Whisper STT (alternativo)
LANGFUSE_SECRET_KEY=sk-lf-...         # Observabilidad
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com

# NO TOCAR — valores por defecto correctos para Docker Compose
# POSTGRES_HOST, POSTGRES_PORT, REDIS_HOST, etc. se setean en docker-compose.yml
```

### 2. Levantar servicios backend

```bash
# Levantar todo (postgres, redis, api, tunnel)
docker compose up -d --build

# Verificar que todos los containers estén healthy
docker compose ps
```

Deberías ver:
```
ai-host-agent            Up (healthy)
ai-host-agent-postgres   Up (healthy)
ai-host-agent-redis      Up (healthy)
ai-host-agent-tunnel     Up
```

### 3. Verificar que la API funciona

```bash
# Health check
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}

# Probar el agente por chat
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hola, quiero reservar una mesa","session_id":"test-001"}'
```

### 4. Configurar Twilio (para llamadas de voz)

#### a. Obtener la URL del tunnel

```bash
docker compose logs tunnel | grep "trycloudflare.com"
# → https://xxxxx-yyyy-zzzz.trycloudflare.com
```

#### b. Actualizar .env con la URL del tunnel

```bash
# Editar .env y poner la URL del tunnel en TWILIO_WEBHOOK_BASE_URL
# Ejemplo: TWILIO_WEBHOOK_BASE_URL=https://xxxxx-yyyy-zzzz.trycloudflare.com
```

#### c. Recrear el container API (para que tome la nueva URL)

```bash
docker compose up -d api
```

#### d. Configurar webhook en Twilio Console

1. Ir a [Twilio Console](https://console.twilio.com) → Phone Numbers → Manage → Active Numbers
2. Click en tu número
3. En **Voice & Fax** → **"A CALL COMES IN"**:
   - Webhook: `https://tu-tunnel-url/api/v1/voice/inbound`
   - Método: HTTP POST
4. Save

> **Nota:** La URL del tunnel cambia cada vez que se reinicia el container `tunnel`. Después de cada reinicio hay que:
> 1. Obtener la nueva URL (`docker compose logs tunnel | grep trycloudflare`)
> 2. Actualizar `TWILIO_WEBHOOK_BASE_URL` en `.env`
> 3. `docker compose up -d api` (recrear container)
> 4. Actualizar el webhook en Twilio Console

### 5. Levantar el dashboard (UI)

```bash
cd ui
npm install
npm run dev
# → http://localhost:5173
```

Usuarios por defecto:
| Usuario | Password | Rol |
|---------|----------|-----|
| admin | 1234 | admin |
| writer | 1234 | writer |
| reader | 1234 | reader |

### 6. Cargar datos de ejemplo (opcional)

```bash
# Desde la raíz del proyecto, con los containers corriendo
python3 scripts/seed_sample_reservations.py
```

Esto carga ~30 reservas por día con nombres, horarios y preferencias variadas.

### 7. Hacer una llamada de prueba

Si no podés llamar directamente al número Twilio, podés hacer que Twilio te llame:

```bash
curl -X POST "https://api.twilio.com/2010-04-01/Accounts/TU_ACCOUNT_SID/Calls.json" \
  --data-urlencode "To=+TU_NUMERO_CELULAR" \
  --data-urlencode "From=+TU_NUMERO_TWILIO" \
  --data-urlencode "Url=https://tu-tunnel-url/api/v1/voice/inbound" \
  -u "TU_ACCOUNT_SID:TU_AUTH_TOKEN"
```

---

## Comandos útiles

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Ver logs solo de la API
docker compose logs -f api

# Shell dentro del container API
docker compose exec api bash

# Shell de PostgreSQL
docker compose exec postgres psql -U hostai_user -d hostai_db

# Shell de Redis
docker compose exec redis redis-cli

# Correr tests
docker compose exec api pytest tests/ -v --cov=src

# Correr solo unit tests
docker compose exec api pytest tests/unit/ -v

# Parar todo
docker compose down

# Parar y borrar volúmenes (CUIDADO: borra datos de PostgreSQL)
docker compose down -v

# Rebuild completo
docker compose up -d --build
```

O usando el Makefile:

```bash
make up          # Levantar todo
make down        # Parar todo
make logs        # Logs de la API
make test        # Correr tests
make shell       # Bash en el container
make db-shell    # psql
make redis-cli   # redis-cli
make clean       # Borrar todo (containers + volúmenes + imágenes)
make demo        # Correr demo portfolio
```

---

## API Reference

| Método | Endpoint | Auth | Descripción |
|--------|----------|------|-------------|
| `GET` | `/health` | No | Health check |
| `POST` | `/api/v1/auth/token` | No | Login (OAuth2 password) |
| `GET` | `/api/v1/reservations` | API Key | Listar reservas (filtros + paginación) |
| `POST` | `/api/v1/reservations` | API Key | Crear reserva |
| `GET` | `/api/v1/reservations/{id}` | API Key | Obtener reserva por ID |
| `PATCH` | `/api/v1/reservations/{id}/status` | API Key | Cambiar estado (confirmed/seated/no_show/cancelled) |
| `DELETE` | `/api/v1/reservations/{id}` | API Key | Cancelar reserva |
| `GET` | `/api/v1/reservations/stream` | No | SSE stream en tiempo real |
| `POST` | `/api/v1/voice/inbound` | No | Webhook Twilio — llamada entrante |
| `POST` | `/api/v1/voice/process` | No | Webhook Twilio — procesar speech |
| `POST` | `/api/v1/voice/outbound/{id}` | API Key | Llamada saliente de confirmación |
| `GET` | `/api/v1/audio/{uid}` | No | Servir audio TTS generado |
| `POST` | `/api/v1/agent/chat` | No | Chat con el agente (texto) |
| `GET` | `/api/v1/floor-plan` | No | Obtener plano del restaurante |
| `PUT` | `/api/v1/floor-plan` | JWT | Guardar plano (requiere permiso) |
| `GET` | `/api/v1/floor-plan/assignments` | No | Asignaciones de mesa por fecha/hora |
| `POST` | `/api/v1/floor-plan/assignments` | JWT | Asignar mesa a reserva |
| `DELETE` | `/api/v1/floor-plan/assignments/{id}` | JWT | Desasignar mesa |
| `GET` | `/api/v1/floor-plan/availability` | No | Mesas disponibles por fecha/hora/sección |
| `PATCH` | `/api/v1/reservations/{id}/confirmation` | API Key | Actualizar estado de confirmación |
| `GET` | `/api/v1/config/confirmation` | No | Config de llamada de confirmación |
| `PATCH` | `/api/v1/config/confirmation` | JWT (admin) | Cambiar lead time de confirmación |

Auth: `X-API-Key: tu-api-key` header, o JWT Bearer token para endpoints de floor plan.

Documentación interactiva: `http://localhost:8000/docs`

---

## Base de datos

**PostgreSQL 16** — Puerto host: `5433`, Container: `5432`

### Tablas

| Tabla | Campos principales |
|-------|-------------------|
| `reservations` | id, reservation_id (UUID), guest_name, guest_phone, date, time, party_size, status, preference, special_requests, notes, created_at, updated_at |
| `call_logs` | id, call_sid (UNIQUE), from_number, to_number, call_status, duration_sec, transcript, intent, created_at |
| `agent_sessions` | id, session_id (UNIQUE), call_sid, messages (JSONB), intent, reservation_data (JSONB), agent_trace (JSONB), created_at, updated_at |
| `floor_plan_assignments` | id, table_id, reservation_id, date, hour, created_at |
| `app_users` | id, username (UNIQUE), password_hash, role, can_edit_floor_plan, created_at |

---

## Dashboard UI

React 18 + Vite + TailwindCSS. Features:

- **Vista de reservas**: Cards con filtros por estado, búsqueda, paginación
- **Floor Plan**: Plano interactivo con React Konva — drag/scroll, asignación de mesas, colores por estado
- **Timeline por hora**: Selector de hora con conteo de reservas, auto-assign inteligente
- **Chat con agente**: Widget de chat integrado (errores se muestran en rojo)
- **SSE en tiempo real**: Las reservas nuevas aparecen automáticamente
- **ErrorBoundary**: Captura errores de render con UI de recuperación
- **i18n**: Español e inglés
- **Dark/Light mode**: Toggle en menú de usuario
- **Auth**: Login con JWT, roles (admin/writer/reader)

---

## Archivos de configuración

| Archivo | Qué configurar |
|---------|---------------|
| `.env` | Todas las credenciales y secrets (NUNCA commitear) |
| `config.yaml` | Configuración estática: modelos LLM, timeouts, voz, reservas |
| `docker-compose.yml` | Servicios, puertos, volúmenes, networking |

---

## Development

```bash
# Correr tests
docker compose exec api pytest tests/ -v

# Lint
docker compose exec api ruff check src/

# Logs
docker compose logs -f api
```

---

## Mejoras recientes

- **Confirmation call flow**: Scheduler automático llama a clientes N minutos antes de su reserva. Tracking de `confirmation_status` (pending/confirmed/declined/no_answer/failed) y `confirmation_called_at` en DB. Botón manual "Call to Confirm" en UI. Config admin para ajustar lead time.
- **Table sections**: Cada mesa tiene un `section` explícito (Patio, Window, Bar, Private, Booth, Quiet, Near Bathroom). Auto-assign respeta preferencias del cliente.
- **Availability endpoint**: `GET /api/v1/floor-plan/availability?date=...&hour=...&party_size=...&section=...` — verifica mesas disponibles por fecha, hora y sección.
- **Agent mejorado**: El agente informa las secciones disponibles durante la toma de reserva y pregunta preferencia de ubicación.
- **Floor plan fixes**: Asignaciones se filtran por hora seleccionada, assign modal muestra solo mesas libres de la hora actual, section visible en lista de mesas.
- **Card detail modal**: Click en una card de reserva abre modal con detalle completo + mesa asignada + acciones.
- **Observabilidad**: Todas las trazas Langfuse etiquetadas con `[HostAI] - {step}` para filtrado fácil
- **Estabilidad**: DB connections con context managers, excepciones logueadas en voice endpoints
- **Seguridad**: JWT secret configurable via `JWT_SECRET_KEY` env var, Pydantic models para todos los request bodies
- **Frontend**: ErrorBoundary global, cleanup de timers en unmount, cajitas de error en rojo en el chat

---

## Troubleshooting

| Problema | Solución |
|----------|---------|
| Container no arranca | `docker compose logs api` para ver el error |
| API no responde | Verificar que postgres y redis estén healthy: `docker compose ps` |
| Llamada no llega al agente | Verificar `TWILIO_WEBHOOK_BASE_URL` y que el tunnel esté corriendo |
| URL del tunnel cambió | Ver nueva URL con `docker compose logs tunnel \| grep trycloudflare`, actualizar .env y Twilio Console |
| TTS suena robótico | Verificar `ELEVENLABS_API_KEY` y `ELEVENLABS_VOICE_ID` en .env |
| Reservas no aparecen en UI | Verificar que el API esté healthy y que el UI proxy apunte a localhost:8000 |
| Login falla | Password por defecto es `1234` para todos los usuarios seed |

---

*Built with [Claude](https://anthropic.com) · [LangGraph](https://langchain-ai.github.io/langgraph/) · [FastAPI](https://fastapi.tiangolo.com/) · [ElevenLabs](https://elevenlabs.io) · [Twilio](https://twilio.com) · [LanceDB](https://lancedb.github.io/lancedb/)*
