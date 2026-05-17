"""Centralised application settings.

A single ``Settings`` class — populated from environment variables and a
``.env`` file — is the only sanctioned source of configuration. This
keeps secrets out of code, makes test overrides trivial (instantiate
``Settings`` directly), and fails fast at startup when something is
misconfigured.

Why a singleton via ``lru_cache``? Pydantic validates on construction;
caching avoids paying that cost on every dependency injection.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid identifiers for the primary AI provider. The actual provider
# implementations live in app.providers and are wired in Phase 1.
ProviderName = Literal["openai", "anthropic", "amaliai"]


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    Fields are read from environment variables (``.env`` is loaded
    automatically). Names map case-insensitively, so ``APP_NAME`` in the
    environment fills ``app_name`` here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Tolerate unrelated env vars (CI, OS-level, etc.).
    )

    # ── Application ─────────────────────────────────────────────────────────
    app_name: str = "LibraryMind"
    app_env: Literal["development", "staging", "production"] = "development"
    app_host: str = "0.0.0.0"  # noqa: S104 - intentional for containerised dev
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── AI providers ────────────────────────────────────────────────────────
    primary_provider: ProviderName = "openai"

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    anthropic_api_key: str | None = None
    anthropic_chat_model: str = "claude-3-5-haiku-latest"

    amaliai_api_key: str | None = None
    amaliai_base_url: str = "https://api.amalitech.org/v1"
    amaliai_chat_model: str = ""

    # ── Vector store ────────────────────────────────────────────────────────
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "books"
    rag_top_k: int = Field(default=4, ge=1, le=20)
    # Similarity threshold (NOT distance). ChromaDB returns cosine distance,
    # which we convert to similarity via `1 - distance` before comparing.
    # 0.0 = unrelated, 1.0 = identical. Results below this are discarded.
    # See docs/ARCHITECTURE.md § Distance vs Similarity for the rationale.
    rag_relevance_threshold: float = Field(default=0.35, ge=0.0, le=1.0)

    # ── Cache ───────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_default_ttl_seconds: int = Field(default=3600, ge=0)
    cache_enabled: bool = True

    # ── Rate limiting ───────────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_burst: int = Field(default=10, ge=1)

    # ── Cost controls ───────────────────────────────────────────────────────
    # Soft daily budget cap in USD. The /health endpoint reports daily spend
    # against this number; in later phases a warning is logged when approaching
    # the limit. A value of 0.0 disables the cap (tracking still happens).
    budget_daily_limit_usd: float = Field(default=0.0, ge=0.0)

    # ── Chatbot ─────────────────────────────────────────────────────────────
    chat_history_max_messages: int = Field(default=10, ge=1, le=100)
    chat_max_tokens: int = Field(default=1024, ge=64, le=8192)

    # ── CORS ────────────────────────────────────────────────────────────────
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    # ------------------------------------------------------------------ helpers
    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins parsed from the comma-separated env value."""
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def configured_providers(self) -> list[ProviderName]:
        """Providers that actually have an API key set, in preference order."""
        ordered: list[ProviderName] = [self.primary_provider]
        for name in ("openai", "anthropic", "amaliai"):
            if name not in ordered:
                ordered.append(name)

        present: list[ProviderName] = []
        for name in ordered:
            if self._has_key(name):
                present.append(name)
        return present

    def _has_key(self, name: ProviderName) -> bool:
        """Whether the named provider has the credentials it needs to run."""
        if name == "openai":
            return bool(self.openai_api_key)
        if name == "anthropic":
            return bool(self.anthropic_api_key)
        if name == "amaliai":
            return bool(self.amaliai_api_key)
        return False  # type: ignore[unreachable]

    # --------------------------------------------------------------- validation
    @model_validator(mode="after")
    def _require_at_least_one_provider_key(self) -> Settings:
        """Application cannot start without at least one usable AI provider.

        Lab Part 0 acceptance criterion: "Config module loads environment
        variables and validates that at least one provider key is set."
        """
        if not self.configured_providers:
            raise ValueError(
                "No AI provider configured. Set at least one of "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, or AMALIAI_API_KEY in "
                "your .env file."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so repeated ``Depends(get_settings)`` calls in FastAPI do not
    re-parse the environment on every request. Tests that need to override
    configuration should clear the cache with ``get_settings.cache_clear()``.
    """
    return Settings()
