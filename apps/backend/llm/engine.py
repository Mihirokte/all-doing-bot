"""Multi-provider LLM engine with Local/Remote/Mock fallback."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
import psutil
from pydantic import BaseModel

from apps.backend.config import settings
from apps.backend.llm.output_parser import parse_and_validate

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Provider strategy interface."""

    provider_name = "base"

    @property
    def available(self) -> bool:
        return True

    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        """Return raw provider output."""


class LocalProvider(LLMProvider):
    """Local GGUF inference via llama-cpp-python with RAM-aware startup."""

    provider_name = "local"

    def __init__(self) -> None:
        self._llm: Any | None = None
        self._available = True
        self._load_attempted = False
        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self._available and settings.model_file_path is not None

    def _ensure_loaded(self) -> None:
        """Blocking model load — must be called from a thread executor."""
        if self._load_attempted:
            return
        self._load_attempted = True
        model_path = settings.model_file_path
        if model_path is None:
            self._available = False
            logger.info("LocalProvider unavailable: MODEL_PATH not set or file missing")
            return
        try:
            required_mb = int((model_path.stat().st_size * 1.1) / (1024 * 1024))
        except OSError as exc:
            self._available = False
            logger.warning("LocalProvider: cannot stat model file: %s", exc)
            return
        available_mb = int(psutil.virtual_memory().available / (1024 * 1024))
        if available_mb < required_mb:
            self._available = False
            logger.warning(
                "Insufficient RAM for local model (%sMB available, %sMB required). Falling back to next provider.",
                available_mb,
                required_mb,
            )
            return
        try:
            from llama_cpp import Llama

            self._llm = Llama(model_path=str(model_path), n_ctx=2048, verbose=False)
        except (ImportError, OSError, MemoryError) as exc:
            self._available = False
            logger.warning("LocalProvider unavailable after model load failure: %s", exc)

    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        # Double-checked locking: load model in executor if not yet attempted
        if not self._load_attempted:
            async with self._lock:
                if not self._load_attempted:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self._ensure_loaded)
        if not self.available or self._llm is None:
            raise RuntimeError("LocalProvider unavailable")
        loop = asyncio.get_event_loop()
        async with self._lock:
            result = await loop.run_in_executor(
                None,
                lambda: self._llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=0.1,
                    stop=["User:", "System:"],
                ),
            )
        choices = result.get("choices") if isinstance(result, dict) else None
        if choices:
            return choices[0].get("text", "").strip()
        return str(result).strip()


class OllamaProvider(LLMProvider):
    """Local Ollama server via native /api/chat endpoint."""

    provider_name = "ollama"

    @property
    def available(self) -> bool:
        return bool(settings.ollama_base_url and settings.ollama_model)

    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        base = settings.ollama_base_url.rstrip("/")
        url = f"{base}/api/chat"
        effective_max_tokens = max(64, min(max_tokens, 512))
        payload = {
            "model": settings.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": effective_max_tokens,
            },
        }
        # qwen3.x thinking models: disable internal reasoning so responses are fast on CPU
        if "qwen3" in (settings.ollama_model or "").lower():
            payload["think"] = False
        async with httpx.AsyncClient(timeout=240.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        msg = data.get("message") if isinstance(data, dict) else None
        if not isinstance(msg, dict):
            raise RuntimeError("Ollama response missing 'message'")
        content = (msg.get("content") or "").strip()
        # For thinking models, fall back to reasoning field if content is empty
        if not content:
            content = (msg.get("thinking") or "").strip()
        return content


class RemoteProvider(LLMProvider):
    """OpenAI-compatible remote API provider (Groq by default)."""

    provider_name = "remote"

    @property
    def available(self) -> bool:
        return bool(settings.remote_llm_api_key)

    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        if not self.available:
            raise RuntimeError("RemoteProvider unavailable: missing API key")
        headers = {
            "Authorization": f"Bearer {settings.remote_llm_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.remote_llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(base_url=settings.remote_llm_base_url, timeout=30.0) as client:
            response = await client.post("/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            try:
                data = response.json()
            except Exception as exc:
                raise RuntimeError("RemoteProvider returned non-JSON response") from exc
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise RuntimeError("RemoteProvider response missing or empty 'choices'")
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(msg, dict):
            raise RuntimeError("RemoteProvider response 'choices[0].message' is missing")
        return msg.get("content", "").strip()


class MockProvider(LLMProvider):
    """Deterministic canned responses for development and tests."""

    provider_name = "mock"

    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        await asyncio.sleep(0)
        if "extract structured intent" in prompt.lower() or "Respond in JSON only" in prompt:
            return (
                '{"cohort_name": "test_cohort", "cohort_description": "Test cohort", '
                '"action_type": "web_fetch", "action_params": {"source": "web", "keyword": "test"}, '
                '"summary": "Fetch test results"}'
            )
        if "task planner" in prompt and '"steps"' in prompt:
            return '{"steps": [{"action": "web_fetch", "params": {"urls": []}}]}'
        if "title" in prompt and "key_fields" in prompt:
            return '{"title": "Test title", "summary": "Test summary", "key_fields": {"source": "mock"}}'
        return "{}"


class LLMEngine:
    """Provider-fallback engine with structured-output helper."""

    def __init__(self) -> None:
        self.providers: list[LLMProvider] = self._build_providers()

    def _build_providers(self) -> list[LLMProvider]:
        provider_map: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(),
            "local": LocalProvider(),
            "remote": RemoteProvider(),
            "mock": MockProvider(),
        }
        providers: list[LLMProvider] = []
        for name in settings.llm_provider_order:
            provider = provider_map.get(name)
            if provider is not None:
                providers.append(provider)
        if not providers:
            providers.append(MockProvider())
        return providers

    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        last_error: Exception | None = None
        for provider in self.providers:
            if not provider.available:
                logger.info("Skipping unavailable provider: %s", provider.provider_name)
                continue
            try:
                logger.debug("Trying provider: %s", provider.provider_name)
                output = await provider.generate(prompt, max_tokens=max_tokens, json_mode=json_mode)
                if output.strip():
                    return output
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if provider.provider_name == "remote":
                    logger.info("Remote API unavailable (%s); proceeding with next provider (e.g. local)", exc)
                elif provider.provider_name == "ollama":
                    logger.info("Ollama unavailable (%s); proceeding with next provider", exc)
                else:
                    logger.warning("Provider %s failed: %s", provider.provider_name, exc)
        if last_error is not None:
            raise RuntimeError(f"All LLM providers failed: {last_error}") from last_error
        raise RuntimeError("No LLM providers available")

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        max_retries: int = 1,
    ) -> BaseModel | None:
        raw_outputs: list[str] = []
        raw = await self.generate(prompt, json_mode=True)
        raw_outputs.append(raw)
        parsed = parse_and_validate(raw, schema)
        if parsed is not None:
            return parsed
        if max_retries <= 0:
            logger.error("Structured generation failed for %s. Raw outputs: %s", schema.__name__, raw_outputs)
            return None
        fields = ", ".join(
            f"{name}: {getattr(field.annotation, '__name__', str(field.annotation))}"
            for name, field in schema.model_fields.items()
        )
        corrective_prompt = (
            "Your previous response was not valid JSON matching the required schema.\n"
            f"Required fields: {fields}\n"
            "Respond with ONLY a JSON object, no other text.\n"
            f"Original request: {prompt}"
        )
        corrected = await self.generate_structured(corrective_prompt, schema, max_retries=max_retries - 1)
        if corrected is None:
            logger.error("Structured retry failed for %s. Raw outputs: %s", schema.__name__, raw_outputs)
        return corrected


_engine: LLMEngine | None = None


def get_llm() -> LLMEngine:
    """Backward-compatible accessor used by the pipeline stages."""
    global _engine
    if _engine is None:
        _engine = LLMEngine()
    return _engine
