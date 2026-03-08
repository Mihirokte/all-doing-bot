"""Real LLM via llama-cpp-python. Optional dependency; used when MODEL_PATH is set."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.backend.config import settings

logger = logging.getLogger(__name__)


class RealLLM:
    """llama-cpp-python wrapper. Load model once, expose generate()."""

    def __init__(self) -> None:
        path = settings.model_path
        if not path:
            raise ValueError("MODEL_PATH not set")
        try:
            from llama_cpp import Llama
            self._llm = Llama(model_path=path, n_ctx=2048, verbose=False)
        except ImportError as e:
            raise RuntimeError("llama-cpp-python not installed") from e
        self._lock = asyncio.Lock()

    async def generate(self, prompt: str, max_tokens: int = 256, json_mode: bool = True) -> str:
        loop = asyncio.get_event_loop()
        # Run in thread pool to avoid blocking
        async with self._lock:
            out = await loop.run_in_executor(
                None,
                lambda: self._llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=0.1,
                    stop=["User:", "System:"],
                ),
            )
        if isinstance(out, dict) and "choices" in out and out["choices"]:
            text = out["choices"][0].get("text", "")
        else:
            text = str(out)
        return text.strip()
