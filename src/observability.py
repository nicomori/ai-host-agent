"""
Step 11 — Langfuse + LangGraph Studio observability (HostAI).

Integrates Langfuse v4 tracing into the HostAI multi-agent pipeline.
Uses the official v4 API: `observe` decorator + `Langfuse` client.
Fails gracefully when LANGFUSE_PUBLIC_KEY env var is absent.

Components:
  is_langfuse_configured()   : check if env vars present
  get_langfuse_client()      : return Langfuse() or None
  observe_agent              : @observe alias with as_type="agent"
  observe_tool               : @observe alias with as_type="tool"
  trace_session              : context-manager to create a root trace
  flush_traces               : flush pending spans on shutdown
  LangfuseConfig             : dataclass with all Langfuse settings
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Generator, Optional

# Form 1: graceful fallback when langfuse is not installed
try:
    from langfuse import Langfuse, observe  # type: ignore[import]
    _LANGFUSE_AVAILABLE = True
except ImportError:
    Langfuse = None  # type: ignore[assignment,misc]
    observe = lambda **kw: (lambda fn: fn)  # type: ignore[assignment]
    _LANGFUSE_AVAILABLE = False

# LangChain/LangGraph callback handler (auto-instruments every node)
try:
    from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler  # type: ignore[import]
    _LANGFUSE_CALLBACK_AVAILABLE = True
except ImportError:
    try:
        from langfuse.callback import CallbackHandler as LangfuseCallbackHandler  # type: ignore[import]
        _LANGFUSE_CALLBACK_AVAILABLE = True
    except ImportError:
        LangfuseCallbackHandler = None  # type: ignore[assignment]
        _LANGFUSE_CALLBACK_AVAILABLE = False

# ─── Configuration ────────────────────────────────────────────────────────────

@dataclass
class LangfuseConfig:
    """Langfuse integration configuration."""
    enabled: bool = True
    capture_input: bool = True
    capture_output: bool = True
    # Resolved from env vars at instantiation time
    public_key: str = field(default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", ""))
    host: str = field(default_factory=lambda: os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"))


def is_langfuse_configured() -> bool:
    """Return True iff LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY")
        and os.getenv("LANGFUSE_SECRET_KEY")
    )


_langfuse_client: Optional[Langfuse] = None


def get_langfuse_client() -> Optional[Langfuse]:
    """
    Return the singleton Langfuse client, or None if not configured/available.
    Thread-safe for read-only singleton (module-level init is sufficient
    for our single-process use case).
    """
    global _langfuse_client
    if not _LANGFUSE_AVAILABLE or not is_langfuse_configured():
        return None
    if _langfuse_client is None:
        _langfuse_client = Langfuse()
    return _langfuse_client


def flush_traces() -> None:
    """Flush any pending Langfuse traces.  No-op if not configured."""
    client = get_langfuse_client()
    if client is not None:
        client.flush()


# ─── Decorator helpers ────────────────────────────────────────────────────────

def observe_agent(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    @observe_agent wraps a node function as a Langfuse 'agent' span.
    Falls back to identity decorator when Langfuse is not configured.

    Usage:
        @observe_agent
        def reservation_agent(state): ...

        @observe_agent(name="custom_agent_name")
        def some_fn(state): ...
    """
    def decorator(fn: Callable) -> Callable:
        if not _LANGFUSE_AVAILABLE or not is_langfuse_configured():
            return fn
        span_name = name or fn.__name__
        return observe(name=span_name, as_type="agent")(fn)

    if func is not None:
        # Called as @observe_agent (no parentheses)
        return decorator(func)
    # Called as @observe_agent(name=...) — return the decorator
    return decorator


def observe_tool(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    @observe_tool wraps a function as a Langfuse 'tool' span.
    Falls back to identity decorator when Langfuse is not configured.
    """
    def decorator(fn: Callable) -> Callable:
        if not _LANGFUSE_AVAILABLE or not is_langfuse_configured():
            return fn
        return observe(name=name or fn.__name__, as_type="tool")(fn)

    if func is not None:
        return decorator(func)
    return decorator


def observe_fn(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    Generic @observe wrapper. Creates a Langfuse span for any function.
    Falls back to identity decorator when Langfuse is not available.
    """
    def decorator(fn: Callable) -> Callable:
        if not _LANGFUSE_AVAILABLE or not is_langfuse_configured():
            return fn
        return observe(name=name or fn.__name__)(fn)

    if func is not None:
        return decorator(func)
    return decorator


# ─── Context-manager trace ────────────────────────────────────────────────────

@contextmanager
def trace_session(
    session_id: str,
    user_message: str = "",
    metadata: Optional[dict] = None,
) -> Generator[Optional[Any], None, None]:
    """
    Context manager that creates a root Langfuse trace for a session.
    Yields the trace ID (or None if Langfuse is not configured).

    In Langfuse v4 the tracing is handled automatically via @observe decorators
    and the LangChain CallbackHandler. This context manager just ensures
    a flush happens after the session completes.

    Usage:
        with trace_session(session_id=sid, user_message=msg) as trace_id:
            result = invoke_agent(...)
    """
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    trace_id = client.create_trace_id()
    try:
        yield trace_id
    finally:
        client.flush()


# ─── Span helpers (for manual instrumentation) ────────────────────────────────

def create_span(
    name: str,
    trace_id: Optional[str] = None,
    input_data: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> Optional[Any]:
    """
    Create a Langfuse span for manual instrumentation.
    Returns the span object or None if Langfuse not configured.
    """
    client = get_langfuse_client()
    if client is None:
        return None
    kwargs: dict[str, Any] = {"name": name}
    if input_data:
        kwargs["input"] = input_data
    if metadata:
        kwargs["metadata"] = metadata
    return client.span(**kwargs)


def record_event(
    name: str,
    output: Optional[dict] = None,
    level: str = "DEFAULT",
) -> None:
    """Record a Langfuse event.  No-op if not configured."""
    client = get_langfuse_client()
    if client is None:
        return
    client.event(name=name, output=output or {}, level=level)


# ─── LangGraph callback handler ─────────────────────────────────────────────

def get_langfuse_callback_handler(
    session_id: Optional[str] = None,
) -> Optional[Any]:
    """
    Return a Langfuse CallbackHandler for LangGraph/LangChain.
    This auto-instruments every node (supervisor, sub-agents) as spans.
    Returns None if Langfuse is not configured or callback not available.
    """
    if not _LANGFUSE_CALLBACK_AVAILABLE or not is_langfuse_configured():
        return None
    return LangfuseCallbackHandler()
