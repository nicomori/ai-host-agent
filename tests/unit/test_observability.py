"""
Step 11 — Langfuse + LangGraph Studio observability tests (ai-host-agent).

7 test cases:
  TC1: is_langfuse_configured() returns False when env vars absent
  TC2: is_langfuse_configured() returns True when env vars set
  TC3: get_langfuse_client() returns None when not configured
  TC4: get_langfuse_client() returns Langfuse instance when configured
  TC5: observe_agent decorator is identity when Langfuse not configured
  TC6: observe_tool decorator is identity when Langfuse not configured
  TC7: trace_session context manager yields None when not configured
       and runs the body without error
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch


from src.observability import (
    LangfuseConfig,
    create_span,
    flush_traces,
    get_langfuse_client,
    is_langfuse_configured,
    observe_agent,
    observe_tool,
    record_event,
    trace_session,
)


# ══════════════════════════════════════════════════════════════════════════════
# TC1 — is_langfuse_configured() → False when env vars absent
# ══════════════════════════════════════════════════════════════════════════════


def test_tc1_not_configured_when_no_env_vars():
    """
    With LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY unset,
    is_langfuse_configured() must return False.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }
    with patch.dict(os.environ, env, clear=True):
        result = is_langfuse_configured()
    print(f"\nTC1 is_langfuse_configured (no env): {result}")
    assert result is False


def test_tc1_not_configured_partial_env():
    """Only public key set — still returns False."""
    with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk-test"}, clear=False):
        original_secret = os.environ.pop("LANGFUSE_SECRET_KEY", None)
        try:
            result = is_langfuse_configured()
        finally:
            if original_secret:
                os.environ["LANGFUSE_SECRET_KEY"] = original_secret
    assert result is False


# ══════════════════════════════════════════════════════════════════════════════
# TC2 — is_langfuse_configured() → True when env vars set
# ══════════════════════════════════════════════════════════════════════════════


def test_tc2_configured_when_both_env_vars_set():
    """
    With both LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY set,
    is_langfuse_configured() must return True.
    """
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_PUBLIC_KEY": "pk-test-public",
            "LANGFUSE_SECRET_KEY": "sk-test-secret",
        },
    ):
        result = is_langfuse_configured()
    print(f"\nTC2 is_langfuse_configured (both set): {result}")
    assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# TC3 — get_langfuse_client() → None when not configured
# ══════════════════════════════════════════════════════════════════════════════


def test_tc3_get_client_returns_none_when_not_configured():
    """
    get_langfuse_client() must return None when Langfuse is not configured.
    No exception must be raised.
    """
    import src.observability as obs_module

    original_client = obs_module._langfuse_client
    obs_module._langfuse_client = None

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }
    try:
        with patch.dict(os.environ, env, clear=True):
            client = get_langfuse_client()
    finally:
        obs_module._langfuse_client = original_client

    print(f"\nTC3 get_langfuse_client (no config): {client}")
    assert client is None


# ══════════════════════════════════════════════════════════════════════════════
# TC4 — get_langfuse_client() → Langfuse instance when configured
# ══════════════════════════════════════════════════════════════════════════════


def test_tc4_get_client_returns_langfuse_when_configured():
    """
    When env vars are set and Langfuse() constructor is mocked,
    get_langfuse_client() must return a Langfuse instance.
    """
    import src.observability as obs_module

    original_client = obs_module._langfuse_client
    obs_module._langfuse_client = None

    mock_instance = MagicMock()
    with patch.dict(
        os.environ,
        {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        },
    ):
        with patch("src.observability.Langfuse", return_value=mock_instance) as mock_cls:
            client = get_langfuse_client()
            mock_cls.assert_called_once()

    obs_module._langfuse_client = original_client

    print(f"\nTC4 get_langfuse_client (configured): {client}")
    assert client is mock_instance


# ══════════════════════════════════════════════════════════════════════════════
# TC5 — observe_agent is identity decorator when not configured
# ══════════════════════════════════════════════════════════════════════════════


def test_tc5_observe_agent_identity_when_not_configured():
    """
    When Langfuse is not configured, @observe_agent must return the
    original function unchanged (no wrapping overhead).
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    def my_agent(state):
        return {"result": "agent_ran"}

    with patch.dict(os.environ, env, clear=True):
        wrapped = observe_agent(my_agent)

    print(f"\nTC5 observe_agent wrapped: {wrapped}")
    # When not configured, should return the original function
    assert wrapped is my_agent
    # Calling it must work
    assert wrapped({"messages": []}) == {"result": "agent_ran"}


def test_tc5_observe_agent_with_name_param():
    """observe_agent(name=...) syntax must also work."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    def my_agent(state):
        return {}

    with patch.dict(os.environ, env, clear=True):
        decorator = observe_agent(name="custom_agent")
        wrapped = decorator(my_agent)

    assert wrapped is my_agent


# ══════════════════════════════════════════════════════════════════════════════
# TC6 — observe_tool is identity decorator when not configured
# ══════════════════════════════════════════════════════════════════════════════


def test_tc6_observe_tool_identity_when_not_configured():
    """
    When Langfuse is not configured, @observe_tool must return the
    original function unchanged.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    def lookup_reservation(reservation_id: str) -> dict:
        return {"reservation_id": reservation_id, "status": "confirmed"}

    with patch.dict(os.environ, env, clear=True):
        wrapped = observe_tool(lookup_reservation)

    print(f"\nTC6 observe_tool wrapped: {wrapped}")
    assert wrapped is lookup_reservation
    result = wrapped("RES-001")
    assert result["status"] == "confirmed"


# ══════════════════════════════════════════════════════════════════════════════
# TC7 — trace_session yields None when not configured
# ══════════════════════════════════════════════════════════════════════════════


def test_tc7_trace_session_yields_none_when_not_configured():
    """
    When Langfuse is not configured, trace_session must yield None
    and not raise any exception.  The body must execute normally.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    sid = str(uuid.uuid4())
    body_ran = False

    with patch.dict(os.environ, env, clear=True):
        with trace_session(session_id=sid, user_message="test message") as trace:
            body_ran = True
            print(f"\nTC7 trace object: {trace}")
            assert trace is None

    assert body_ran, "Context manager body must execute even when Langfuse is not configured"


def test_tc7_trace_session_with_metadata():
    """trace_session with metadata kwarg must not raise."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    with patch.dict(os.environ, env, clear=True):
        with trace_session(
            session_id=str(uuid.uuid4()),
            user_message="book a table",
            metadata={"env": "test", "version": "1.0"},
        ) as trace:
            assert trace is None  # no Langfuse client configured


def test_tc7_flush_traces_noop_when_not_configured():
    """flush_traces() must not raise when Langfuse is not configured."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    with patch.dict(os.environ, env, clear=True):
        import src.observability as obs_module

        original = obs_module._langfuse_client
        obs_module._langfuse_client = None
        try:
            flush_traces()  # must not raise
        finally:
            obs_module._langfuse_client = original


# ══════════════════════════════════════════════════════════════════════════════
# Extra — LangfuseConfig dataclass
# ══════════════════════════════════════════════════════════════════════════════


def test_langfuse_config_defaults():
    """LangfuseConfig must have sensible defaults."""
    config = LangfuseConfig()
    assert config.enabled is True
    assert config.capture_input is True
    assert config.capture_output is True
    assert "langfuse.com" in config.host


def test_langfuse_config_custom_host():
    """LangfuseConfig must accept custom host via env var."""
    with patch.dict(os.environ, {"LANGFUSE_HOST": "https://self-hosted.example.com"}):
        config = LangfuseConfig()
    assert config.host == "https://self-hosted.example.com"


def test_create_span_returns_none_when_not_configured():
    """create_span() must return None when Langfuse not configured."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    with patch.dict(os.environ, env, clear=True):
        import src.observability as obs_module

        original = obs_module._langfuse_client
        obs_module._langfuse_client = None
        try:
            span = create_span("test_span", input_data={"session_id": "test-001"})
        finally:
            obs_module._langfuse_client = original

    assert span is None


def test_record_event_noop_when_not_configured():
    """record_event() must not raise when Langfuse not configured."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    }

    with patch.dict(os.environ, env, clear=True):
        import src.observability as obs_module

        original = obs_module._langfuse_client
        obs_module._langfuse_client = None
        try:
            record_event("reservation_created", output={"status": "confirmed"})
        finally:
            obs_module._langfuse_client = original
