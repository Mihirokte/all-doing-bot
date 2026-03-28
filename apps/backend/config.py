"""All configuration from environment variables. No hardcoded secrets."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Sheets (Drive + Sheets APIs: find or create spreadsheet by name)
    google_creds_path: str = ""
    spreadsheet_id: str = ""
    # If set, find existing spreadsheet by this title or create it. Ignored when SPREADSHEET_ID is set.
    google_sheets_spreadsheet_name: str = "all-doing-bot cohorts"
    # Transient API failures (429, 5xx, timeouts): retry sync gspread calls in a thread.
    google_sheets_retry_attempts: int = 3
    google_sheets_retry_base_delay_seconds: float = 1.0
    # Minimum seconds between HTTP GETs to the same host (implementation plan: polite fetching).
    fetch_min_interval_seconds_per_domain: float = 1.0

    # LLM provider selection (ollama = local Ollama server, e.g. qwen3.5:4b)
    # Default is local-first Qwen runtime; remote provider is opt-in only.
    llm_provider_priority: str = "ollama,local"
    model_path: str = ""
    # Ollama (local server, OpenAI-compatible at /v1/chat/completions)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    remote_llm_api_key: str = ""
    remote_llm_base_url: str = "https://api.groq.com/openai/v1"
    remote_llm_model: str = "llama-3.1-8b-instant"
    # SearXNG (web search, optional)
    searxng_base_url: str = "http://localhost:8888"
    # Cloudflare Browser Rendering (optional): crawl URLs for full Markdown. When set, used to enrich search or fetch.
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""

    # Extractor / site adapter settings
    nitter_instances: List[str] = Field(
        default_factory=lambda: [
            "https://nitter.net",
            "https://nitter.poast.org",
            "https://nitter.privacydev.net",
        ]
    )

    # Web search in chat: default on (SearXNG/MCP/deep search). Set CHAT_WEB_SEARCH_ENABLED=false to disable.
    chat_web_search_enabled: bool = True
    # Structured LLM gate for /chat: needs_web + search query rewrite + vague-query clarification.
    chat_web_gate_enabled: bool = True
    # Deep Think-Do retrieval (short search queries: 3-cycle loop, evidence-first). Only used when chat_web_search_enabled is True.
    chat_deep_mode_enabled: bool = True
    chat_deep_max_cycles: int = 3
    chat_deep_top_links: int = 4

    # Redis (optional): step queue + shared task_store (GET /status across API replicas) when reachable; workers consume the step queue.
    redis_url: str = ""
    # Executor mode: queue-first by default, legacy in-process path is fallback only.
    orchestrator_legacy_fallback_enabled: bool = False
    # Queue orchestration tuning.
    queue_step_poll_interval_seconds: float = 1.5
    queue_step_poll_timeout_seconds: float = 300.0
    # Search: default is MCP (required stack). Set CONNECTOR_SEARCH_DEFAULT_PROVIDER=searxng only if you intentionally use SearXNG instead.
    connector_search_default_provider: str = "mcp"
    # Required when provider is mcp: JSON array of argv to start your MCP server (stdio), e.g. '["npx","-y","your-mcp-server"]'.
    mcp_search_command_json: str = ""
    mcp_search_tool_name: str = "search"
    mcp_search_query_param: str = "query"
    connector_fetch_default_provider: str = "cloudflare"
    connector_browser_default_provider: str = "cloudflare_browser"
    # Policy engine (CSV lists).
    policy_deny_actions: str = ""
    policy_require_approval_actions: str = "browser_automation"
    policy_allowed_hosts: str = ""
    policy_denied_hosts: str = ""
    policy_auto_approve: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    # Set CORS_ALLOW_ORIGINS in production to your frontend origin (e.g. GitHub Pages URL). Comma-separated.
    cors_allow_origins: str = "https://mihirokte.github.io,http://localhost:3000,http://127.0.0.1:3000"

    @property
    def credentials_path(self) -> Optional[Path]:
        if not self.google_creds_path:
            return None
        path = Path(self.google_creds_path)
        return path if path.exists() else None

    @property
    def model_file_path(self) -> Optional[Path]:
        if not self.model_path:
            return None
        path = Path(self.model_path)
        return path if path.exists() else None

    @property
    def llm_provider_order(self) -> List[str]:
        return [part.strip().lower() for part in self.llm_provider_priority.split(",") if part.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def mcp_search_argv(self) -> List[str]:
        raw = (self.mcp_search_command_json or "").strip()
        if not raw:
            return []
        try:
            v = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(
                "MCP_SEARCH_COMMAND_JSON is set but contains invalid JSON: %s",
                raw[:200],
            )
            return []
        if not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v):
            logger.error(
                "MCP_SEARCH_COMMAND_JSON must be a JSON array of strings, got: %s",
                type(v).__name__,
            )
            return []
        return list(v)

    @property
    def configured_providers(self) -> List[str]:
        """Return list of LLM providers that have their required env vars set."""
        configured = []
        # ollama has a default base URL, so it's always nominally configured
        configured.append("ollama")
        if self.model_path:
            configured.append("local")
        if self.remote_llm_api_key:
            configured.append("remote")
        return configured

    @model_validator(mode="after")
    def _validate_config(self) -> Settings:
        # Validate MCP argv when MCP provider is selected
        prov = (self.connector_search_default_provider or "").strip().lower()
        if prov == "mcp":
            raw = (self.mcp_search_command_json or "").strip()
            if raw:
                try:
                    v = json.loads(raw)
                except json.JSONDecodeError:
                    raise ValueError(
                        "MCP_SEARCH_COMMAND_JSON contains invalid JSON. "
                        "Must be a JSON array of strings, e.g. "
                        '[\"npx\",\"-y\",\"@your/mcp-server\"].'
                    )
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    raise ValueError(
                        "MCP_SEARCH_COMMAND_JSON must be a JSON array of strings, "
                        f"got {type(v).__name__}. Example: "
                        '[\"npx\",\"-y\",\"@your/mcp-server\"].'
                    )
            if not self.mcp_search_argv:
                raise ValueError(
                    "CONNECTOR_SEARCH_DEFAULT_PROVIDER is mcp but MCP_SEARCH_COMMAND_JSON is missing or invalid. "
                    "Set MCP_SEARCH_COMMAND_JSON to a JSON array of command argv, e.g. "
                    '[\"npx\",\"-y\",\"@your/mcp-server\"].'
                )
        # Log provider configuration status
        configured = self.configured_providers
        requested = self.llm_provider_order
        logger.info(
            "LLM providers configured: %s | requested priority: %s",
            configured, requested,
        )
        not_configured = [p for p in requested if p not in configured]
        if not_configured:
            logger.warning(
                "Requested LLM providers not configured (missing env vars): %s",
                not_configured,
            )
        return self


settings = Settings()
