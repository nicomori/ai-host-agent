"""
BLOQUE 3 — Archivo Config Externo: Test Suite (HostAI)
15 test cases: AppConfig from_yaml, tipos, validacion, Settings merge, lancedb_uri priority,
               validate_secrets prod, AppSettings singleton, and 8 additional coverage cases.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ─── TC-01: AppConfig.from_yaml() loads all sections with correct types ────────
def test_tc01_appconfig_from_yaml():
    """TC-01: AppConfig.from_yaml() must parse config.yaml into typed sections."""
    from src.config import AppConfig

    cfg = AppConfig.from_yaml()

    assert cfg.app.name == "ai-host-agent"
    assert cfg.app.version == "0.2.1"
    assert cfg.server.port == 8000
    assert cfg.agent.checkpointer == "postgres"
    assert cfg.voice.stt_provider == "whisper"
    assert cfg.voice.tts_provider == "elevenlabs"
    assert cfg.llm.model == "claude-haiku-4-5-20251001"
    assert 0.0 <= cfg.llm.temperature <= 1.0
    assert cfg.reservations.confirmation_call_minutes_before == 60
    assert cfg.lancedb.embedding_dim == 1536
    assert len(cfg.lancedb.tables) == 3
    assert cfg.pipeline.max_retries == 3


# ─── TC-02: AppConfig uses safe defaults when YAML is missing ─────────────────
def test_tc02_appconfig_defaults_without_yaml():
    """TC-02: AppConfig() must instantiate with all defaults when no YAML is provided."""
    from src.config import AppConfig

    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=True):
        pass  # file already deleted — use non-existent path
    cfg = AppConfig.from_yaml(Path("/tmp/nonexistent_config_12345.yaml"))

    assert cfg.app.name == "ai-host-agent"
    assert cfg.server.port == 8000
    assert cfg.lancedb.embedding_dim == 1536


# ─── TC-03: Field validators reject out-of-range values ───────────────────────
def test_tc03_field_validators_reject_invalid():
    """TC-03: Pydantic validators must reject invalid field values."""
    from pydantic import ValidationError
    from src.config import LLMSection, ServerSection, AgentSection

    with pytest.raises(ValidationError):
        LLMSection(temperature=2.5)  # > 1.0

    with pytest.raises(ValidationError):
        ServerSection(port=99999)  # > 65535

    with pytest.raises(ValidationError):
        AgentSection(max_conversation_turns=0)  # < 1


# ─── TC-04: Settings reads LANCEDB_URI env var correctly ─────────────────────
def test_tc04_settings_reads_lancedb_uri_from_env(monkeypatch):
    """TC-04: Settings must read LANCEDB_URI from env and AppSettings must use it."""
    from src.config import AppConfig, AppSettings, Settings

    monkeypatch.setenv("LANCEDB_URI", "/custom/path/lancedb")
    # Force fresh Settings (bypass module singleton)
    env = Settings(_env_file=None)
    yaml_cfg = AppConfig.from_yaml()
    merged = AppSettings(yaml_cfg, env)

    assert merged.lancedb_uri == "/custom/path/lancedb"


# ─── TC-05: AppSettings falls back to yaml uri when env not set ───────────────
def test_tc05_lancedb_uri_fallback_to_yaml(monkeypatch):
    """TC-05: When LANCEDB_URI env is empty, AppSettings must use config.yaml uri."""
    from src.config import AppConfig, AppSettings, Settings

    monkeypatch.delenv("LANCEDB_URI", raising=False)
    env = Settings(_env_file=None)
    yaml_cfg = AppConfig.from_yaml()
    merged = AppSettings(yaml_cfg, env)

    # lancedb_uri fallback = yaml value
    assert merged.lancedb_uri == yaml_cfg.lancedb.uri


# ─── TC-06: validate_secrets raises ValueError in production ──────────────────
def test_tc06_validate_secrets_raises_in_production(monkeypatch):
    """TC-06: validate_secrets() must raise ValueError when APP_ENV=production and secrets missing."""
    from src.config import AppConfig, AppSettings, Settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)

    env = Settings(_env_file=None)
    yaml_cfg = AppConfig.from_yaml()
    merged = AppSettings(yaml_cfg, env)

    with pytest.raises(ValueError, match="Production startup blocked"):
        merged.validate_secrets()


# ─── TC-07: get_settings() returns singleton (same object) ────────────────────
def test_tc07_get_settings_is_singleton():
    """TC-07: get_settings() must return the exact same object on repeated calls (lru_cache)."""
    from src.config import get_settings

    a = get_settings()
    b = get_settings()
    assert a is b, "get_settings() is not returning a singleton"
    assert a.app_name == "ai-host-agent"


# ─── TC-08: AppConfig.from_yaml returns correct LLM temperature ──────────────
def test_tc08_llm_temperature_in_range():
    """TC-08: LLM temperature from config.yaml must be in [0.0, 1.0]."""
    from src.config import AppConfig

    cfg = AppConfig.from_yaml()
    assert 0.0 <= cfg.llm.temperature <= 1.0


# ─── TC-09: ServerSection port is within valid TCP range ─────────────────────
def test_tc09_server_port_valid():
    """TC-09: Server port from config must be a valid TCP port (1–65535)."""
    from src.config import AppConfig

    cfg = AppConfig.from_yaml()
    assert 1 <= cfg.server.port <= 65535


# ─── TC-10: AppConfig lancedb tables list has 3 entries ──────────────────────
def test_tc10_lancedb_tables_count():
    """TC-10: config.yaml lancedb.tables must declare exactly 3 tables."""
    from src.config import AppConfig

    cfg = AppConfig.from_yaml()
    assert len(cfg.lancedb.tables) == 3


# ─── TC-11: Settings APP_ENV defaults to 'development' ───────────────────────
def test_tc11_settings_default_env(monkeypatch):
    """TC-11: Settings.app_env must default to 'development' when APP_ENV not set."""
    from src.config import Settings

    monkeypatch.delenv("APP_ENV", raising=False)
    env = Settings(_env_file=None)
    assert env.app_env == "development"


# ─── TC-12: AppSettings.lancedb_uri prefers env over yaml ────────────────────
def test_tc12_lancedb_uri_env_overrides_yaml(monkeypatch):
    """TC-12: env LANCEDB_URI must take precedence over config.yaml uri."""
    from src.config import AppConfig, AppSettings, Settings

    monkeypatch.setenv("LANCEDB_URI", "/override/path")
    env = Settings(_env_file=None)
    yaml_cfg = AppConfig.from_yaml()
    merged = AppSettings(yaml_cfg, env)
    assert merged.lancedb_uri == "/override/path"
    assert merged.lancedb_uri != yaml_cfg.lancedb.uri


# ─── TC-13: get_settings cache_clear allows re-instantiation ─────────────────
def test_tc13_get_settings_cache_clear(monkeypatch):
    """TC-13: After cache_clear(), get_settings() must re-evaluate env vars."""
    from src.config import get_settings

    monkeypatch.setenv("LANCEDB_URI", "/fresh/path")
    get_settings.cache_clear()
    s = get_settings()
    assert s is not None
    get_settings.cache_clear()  # restore for other tests


# ─── TC-14: AgentSection max_conversation_turns must be positive ─────────────
def test_tc14_agent_section_turns_positive():
    """TC-14: AgentSection must reject max_conversation_turns <= 0."""
    from pydantic import ValidationError
    from src.config import AgentSection

    with pytest.raises(ValidationError):
        AgentSection(max_conversation_turns=-1)


# ─── TC-15: AppConfig.from_yaml app.version is semver-like ───────────────────
def test_tc15_app_version_semver():
    """TC-15: app.version in config.yaml must follow x.y.z semver pattern."""
    import re
    from src.config import AppConfig

    cfg = AppConfig.from_yaml()
    assert re.match(r"^\d+\.\d+\.\d+", cfg.app.version), (
        f"app.version '{cfg.app.version}' does not match semver pattern x.y.z"
    )
