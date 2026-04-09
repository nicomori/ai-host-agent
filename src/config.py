"""
HostAI — External Configuration System (Step 3)

Architecture:
  config.yaml  → static non-secret defaults  (committed to git)
  .env         → secrets + env overrides      (NOT committed)
  AppConfig    → typed Pydantic model of config.yaml
  Settings     → Pydantic BaseSettings (reads .env + env vars)
  AppSettings  → merged, validated, cached singleton

Priority (highest → lowest):
  process env vars > .env file > config.yaml defaults
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Path resolution ──────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_YAML = _PROJECT_ROOT / "config.yaml"
_ENV_FILE = _PROJECT_ROOT / ".env"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. TYPED MODELS — one per config.yaml section
# ═══════════════════════════════════════════════════════════════════════════════


class AppSection(BaseModel):
    name: str = "ai-host-agent"
    version: str = "0.1.0"


class ServerSection(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = True


class AgentSection(BaseModel):
    max_conversation_turns: int = Field(default=20, ge=1, le=100)
    session_timeout_minutes: int = Field(default=30, ge=1)
    checkpointer: Literal["postgres", "sqlite", "memory"] = "postgres"


class VoiceSection(BaseModel):
    stt_provider: Literal["whisper", "deepgram"] = "whisper"
    tts_provider: Literal["elevenlabs", "openai"] = "elevenlabs"
    language: str = "es"
    silence_threshold_ms: int = Field(default=1500, ge=100)
    audio_sample_rate: int = Field(default=16000, ge=8000)
    audio_format: Literal["wav", "mp3", "ogg"] = "wav"


class LLMSection(BaseModel):
    model: str = "claude-haiku-4-5-20251001"
    fast_model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = Field(default=512, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)


class ReservationsSection(BaseModel):
    confirmation_call_minutes_before: int = Field(default=60, ge=5)
    max_party_size: int = Field(default=20, ge=1, le=100)
    advance_booking_days: int = Field(default=30, ge=1)
    cancellation_window_hours: int = Field(default=2, ge=0)


class TelephonySection(BaseModel):
    provider: Literal["twilio"] = "twilio"


class PersistenceSection(BaseModel):
    checkpoints_table: str = "agent_checkpoints"
    reservations_table: str = "reservations"
    calls_table: str = "call_logs"


class LanceDBSection(BaseModel):
    uri: str = "/app/data/lancedb"
    tables: list[str] = Field(
        default_factory=lambda: ["reservations_vectors", "conversation_memory", "voice_transcripts"]
    )
    embedding_dim: int = Field(default=1536, ge=64)
    search_limit_default: int = Field(default=5, ge=1)
    memory_max_turns: int = Field(default=50, ge=1)


class PipelineSection(BaseModel):
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_wait_seconds: float = Field(default=2.0, ge=0.0)
    tmp_audio_dir: str = "/app/tmp/audio"
    tmp_transcripts_dir: str = "/app/tmp/transcripts"


class AppConfig(BaseModel):
    """Typed representation of config.yaml. All fields have safe defaults."""

    app: AppSection = Field(default_factory=AppSection)
    server: ServerSection = Field(default_factory=ServerSection)
    agent: AgentSection = Field(default_factory=AgentSection)
    voice: VoiceSection = Field(default_factory=VoiceSection)
    llm: LLMSection = Field(default_factory=LLMSection)
    reservations: ReservationsSection = Field(default_factory=ReservationsSection)
    telephony: TelephonySection = Field(default_factory=TelephonySection)
    persistence: PersistenceSection = Field(default_factory=PersistenceSection)
    lancedb: LanceDBSection = Field(default_factory=LanceDBSection)
    pipeline: PipelineSection = Field(default_factory=PipelineSection)

    @classmethod
    def from_yaml(cls, path: Path = _CONFIG_YAML) -> "AppConfig":
        if not path.exists():
            return cls()
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        return cls.model_validate(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PYDANTIC SETTINGS — reads .env + process env vars (secrets only)
# ═══════════════════════════════════════════════════════════════════════════════


class Settings(BaseSettings):
    """Secrets and environment-specific overrides. No defaults for required secrets."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    app_env: Literal["development", "staging", "production"] = "development"

    # LLM secrets
    anthropic_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")

    # Voice secrets
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="")

    # Twilio secrets
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_phone_number: str = Field(default="")
    twilio_webhook_base_url: str = Field(default="http://localhost:8000")

    # Database secrets
    # Individual postgres fields for psycopg2/asyncpg direct access
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5433)
    postgres_db: str = Field(default="hostai_db")
    postgres_user: str = Field(default="hostai_user")
    postgres_password: str = Field(default="hostai_pass_2026")
    database_url: str = Field(
        default="postgresql+asyncpg://hostai_user:hostai_pass_2026@localhost:5433/hostai_db"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # LanceDB — can override config.yaml uri
    lancedb_uri: str = Field(default="")

    # Restaurant metadata
    restaurant_name: str = Field(default="Restaurant")
    restaurant_timezone: str = Field(default="UTC")

    # API key for endpoint authentication (Step 13)
    api_key: str = Field(default="dev-secret-key")

    @field_validator("anthropic_api_key")
    @classmethod
    def warn_missing_anthropic_key(cls, v: str) -> str:
        if not v:
            import warnings

            warnings.warn(
                "ANTHROPIC_API_KEY is not set — LLM calls will fail in production",
                stacklevel=2,
            )
        return v

    def validate_for_production(self) -> list[str]:
        """Returns list of missing required secrets for production."""
        errors: list[str] = []
        required = {
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "twilio_account_sid": "TWILIO_ACCOUNT_SID",
            "twilio_auth_token": "TWILIO_AUTH_TOKEN",
            "elevenlabs_api_key": "ELEVENLABS_API_KEY",
        }
        for field, env_name in required.items():
            if not getattr(self, field):
                errors.append(f"Missing required secret: {env_name}")
        return errors


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MERGED APP SETTINGS — single object used everywhere
# ═══════════════════════════════════════════════════════════════════════════════


class AppSettings:
    """
    Merged configuration object.
    - yaml_config: typed AppConfig from config.yaml
    - env: Pydantic Settings from .env / env vars
    Convenience accessors delegate to the right layer.
    """

    def __init__(self, yaml_config: AppConfig, env: Settings) -> None:
        self.yaml = yaml_config
        self.env = env
        # LanceDB URI: env wins over config.yaml
        self._lancedb_uri = env.lancedb_uri or yaml_config.lancedb.uri

    # ── Convenience props ──────────────────────────────────────────────────────
    @property
    def app_env(self) -> str:
        return self.env.app_env

    @property
    def app_name(self) -> str:
        return self.yaml.app.name

    @property
    def server_port(self) -> int:
        return self.yaml.server.port

    @property
    def lancedb_uri(self) -> str:
        return self._lancedb_uri

    @property
    def llm_model(self) -> str:
        return self.yaml.llm.model

    @property
    def llm_fast_model(self) -> str:
        return self.yaml.llm.fast_model

    @property
    def checkpointer(self) -> str:
        return self.yaml.agent.checkpointer

    @property
    def reservations(self):
        return self.yaml.reservations

    @property
    def restaurant_name(self) -> str:
        return self.env.restaurant_name

    @property
    def api_key(self) -> str:
        return self.env.api_key

    @property
    def is_production(self) -> bool:
        return self.env.app_env == "production"

    def validate_secrets(self) -> None:
        """Raise ValueError in production if required secrets are missing."""
        if self.is_production:
            errors = self.env.validate_for_production()
            if errors:
                raise ValueError(
                    "Production startup blocked — missing secrets:\n"
                    + "\n".join(f"  • {e}" for e in errors)
                )

    def as_dict(self) -> dict:
        return {
            "app_env": self.app_env,
            "app_name": self.app_name,
            "server_port": self.server_port,
            "lancedb_uri": self.lancedb_uri,
            "llm_model": self.llm_model,
            "checkpointer": self.checkpointer,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SINGLETON — cached, lazy-loaded
# ═══════════════════════════════════════════════════════════════════════════════


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    yaml_cfg = AppConfig.from_yaml()
    env_cfg = Settings()
    return AppSettings(yaml_cfg, env_cfg)


# Module-level singleton — used by services
settings: AppSettings = get_settings()
