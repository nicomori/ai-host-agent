"""HostAI — FastAPI application entry point."""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import os
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import get_settings
from src.api.routes import router as api_router
from src.api.auth_users import auth_router, ensure_default_users
from src.services.floor_plan_service import ensure_assignments_table
from src.models.reservation import HealthResponse
from src.services.lancedb_client import LanceDBClient
from src.services import db as pg_db
from src.observability import get_langfuse_client, flush_traces, is_langfuse_configured

log = structlog.get_logger()


# ─── Outbound confirmation job ─────────────────────────────────────────────────

async def _run_outbound_confirmations():
    """Every minute: call guests with reservations within the configured window that haven't been called."""
    cfg = get_settings()
    sid = cfg.env.twilio_account_sid
    token = cfg.env.twilio_auth_token
    from_number = cfg.env.twilio_phone_number
    if not sid or not token or not from_number:
        return

    from datetime import datetime, timezone, timedelta
    from twilio.rest import Client as TwilioClient

    lead_minutes = cfg.reservations.confirmation_call_minutes_before
    now = datetime.now(timezone.utc)
    window_start = now + timedelta(minutes=lead_minutes - 5)
    window_end   = now + timedelta(minutes=lead_minutes + 5)

    rows = pg_db.list_reservations(status_filter="confirmed")
    for r in rows:
        try:
            res_dt = datetime.fromisoformat(f"{r['date']}T{r['time']}:00").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if not (window_start <= res_dt <= window_end):
            continue
        if r.get("confirmation_status") != "pending":
            continue
        try:
            client = TwilioClient(sid, token)
            twiml = (
                f"<Response><Say language='es-ES'>"
                f"Hola {r['guest_name']}. Le llamamos de {cfg.restaurant_name} "
                f"para confirmar su reserva de {r['party_size']} personas "
                f"para hoy a las {r['time']}. ¡Gracias!"
                f"</Say></Response>"
            )
            client.calls.create(to=r["guest_phone"], from_=from_number, twiml=twiml)
            pg_db.update_confirmation_status(r["reservation_id"], "confirmed")
            log.info("[HostAI] - Confirmation call sent", guest=r["guest_name"], phone=r["guest_phone"])
        except Exception as exc:
            pg_db.update_confirmation_status(r["reservation_id"], "failed")
            log.warning("[HostAI] - Confirmation call failed", exc=str(exc), reservation_id=r["reservation_id"])


# ─── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = get_settings()
    log.info("HostAI starting", env=cfg.app_env, restaurant=cfg.restaurant_name)
    cfg.validate_secrets()
    ldb = LanceDBClient(uri=cfg.lancedb_uri)
    ldb.init_tables()
    log.info("LanceDB ready", uri=cfg.lancedb_uri, tables=ldb.list_tables())
    pg_db.init_db()
    ensure_default_users()
    ensure_assignments_table()

    # Step 11: initialize Langfuse observability
    if is_langfuse_configured():
        lf_client = get_langfuse_client()
        log.info("Langfuse connected", configured=True, client=lf_client is not None)
    else:
        log.info("Langfuse not configured — observability disabled")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_outbound_confirmations, IntervalTrigger(minutes=1))
    scheduler.start()
    log.info("scheduler started")

    yield

    # Flush pending Langfuse traces before shutdown
    flush_traces()
    scheduler.shutdown(wait=False)
    log.info("HostAI shutting down")


# ─── App factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(
        title="HostAI",
        description=(
            "Voice-based restaurant reservation agent. "
            "Handles inbound calls, creates/cancels reservations, "
            "and triggers outbound confirmation calls 1 hour before."
        ),
        version=cfg.yaml.app.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request ID + timing middleware ────────────────────────────────────────
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        request.state.request_id = request_id
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=elapsed_ms,
            request_id=request_id,
        )
        return response

    # ── Global error handlers ─────────────────────────────────────────────────
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "bad_request", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        log.error("unhandled_error", exc=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_server_error", "detail": "An unexpected error occurred"},
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1/auth")

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health() -> HealthResponse:
        cfg = get_settings()
        return HealthResponse(
            status="ok",
            app=cfg.app_name,
            env=cfg.app_env,
            restaurant=cfg.restaurant_name,
            version=cfg.yaml.app.version,
        )

    # ── Static UI (built frontend) ─────────────────────────────────────────
    ui_dist = Path(__file__).resolve().parent.parent / "ui" / "dist"
    if ui_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=ui_dist / "assets"), name="ui-assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def serve_spa(path: str):
            file_path = ui_dist / path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(ui_dist / "index.html")

    return app


app = create_app()
