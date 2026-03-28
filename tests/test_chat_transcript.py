"""Chat transcript load/append (memory path when Sheets unavailable)."""
from __future__ import annotations

import asyncio


def test_chat_transcript_roundtrip_memory() -> None:
    from apps.backend.db.chat_transcript import append_transcript_turn, load_transcript_for_prompt

    async def _go() -> None:
        sk = "pytest-chat-transcript-unique"
        await append_transcript_turn(sk, "user", "Reviews of Dhurandhar 2 please")
        await append_transcript_turn(sk, "assistant", "I need a bit more context.")
        await append_transcript_turn(sk, "user", "It's the 2026 Hindi film.")
        block = await load_transcript_for_prompt(sk)
        assert "Dhurandhar" in block
        assert "2026" in block
        assert "context" in block.lower() or "more" in block.lower()

    asyncio.run(_go())
