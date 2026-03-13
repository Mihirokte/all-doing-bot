"""All configuration from environment variables. No hardcoded secrets."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # LLM provider selection (ollama = local Ollama server, e.g. qwen3.5:4b)
    llm_provider_priority: str = "ollama,local,remote,mock"
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


settings = Settings()
