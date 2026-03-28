"""Per-session Ask-mode chat history: Google Sheets when configured, else in-memory memory_store."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from apps.backend.db.catalogue import catalogue
from apps.backend.db.google_client import spreadsheet_available
from apps.backend.db.memory import memory_store
from apps.backend.db.models import Entry
from apps.backend.db.sheets import add_entries, get_entries
from apps.backend.workflows.handlers import cohort_for, ensure_chat_cohort

logger = logging.getLogger(__name__)

_MAX_SNIPPET = 900
_MAX_BLOCK_CHARS = 7000


def _clip(text: str, n: int) -> str:
    t = (text or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


async def load_transcript_for_prompt(session_key: str, *, max_turns: int = 14) -> str:
    """
    Chronological transcript for LLM prompts (User:/Assistant: lines).
    Prefers persisted sheet rows when Google is configured and the chat cohort has data;
    otherwise uses in-process memory_store (same session_key).
    """
    key = (session_key or "default").strip() or "default"
    pairs: list[tuple[str, str]] = []

    if spreadsheet_available():
        name = cohort_for(key, "chat")
        co = await catalogue.get_cohort(name)
        if co is not None and co.entry_count > 0:
            n = min(max(1, max_turns), co.entry_count)
            offset = max(0, co.entry_count - n)
            try:
                rows = await get_entries(name, limit=n, offset=offset)
            except Exception as e:  # noqa: BLE001
                logger.warning("Chat transcript sheet read failed, using memory: %s", e)
                rows = []
            for e in rows:
                role = "user"
                raw_meta = e.metadata if isinstance(e.metadata, str) else json.dumps(e.metadata or {})
                try:
                    md = json.loads(raw_meta) if isinstance(raw_meta, str) else (raw_meta or {})
                    if isinstance(md, dict) and md.get("role") in ("user", "assistant"):
                        role = str(md["role"])
                except (json.JSONDecodeError, TypeError):
                    pass
                c = (e.content or "").strip()
                if c:
                    pairs.append((role, c))

    if not pairs:
        for r in await memory_store.get_short_term_window(key, limit=max_turns):
            if r.role in ("user", "assistant") and (r.content or "").strip():
                pairs.append((r.role, r.content.strip()))

    if not pairs:
        return ""

    lines: list[str] = []
    total = 0
    for role, content in pairs:
        label = "User" if role == "user" else "Assistant"
        piece = _clip(content, _MAX_SNIPPET)
        line = f"{label}: {piece}"
        if total + len(line) > _MAX_BLOCK_CHARS:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines).strip()


async def append_transcript_turn(session_key: str, role: str, content: str) -> None:
    """Append one chat line: always memory_store; also cohort sheet when Google is available."""
    key = (session_key or "default").strip() or "default"
    text = (content or "").strip()
    if not text:
        return
    await memory_store.append_short_term(key, role, text, tags=["chat"])
    if not spreadsheet_available():
        return
    try:
        cohort_name = await ensure_chat_cohort(key)
        now = datetime.now(timezone.utc).isoformat()
        entry = Entry(
            content=text[:15000],
            source="chat",
            metadata=json.dumps({"role": role, "kind": "chat"}),
            created_at=now,
        )
        await add_entries(cohort_name, [entry])
        existing = await catalogue.get_cohort(cohort_name)
        if existing:
            await catalogue.update_cohort(
                cohort_name,
                {"entry_count": existing.entry_count + 1, "last_run": now},
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("Chat transcript sheet append failed (memory still has turn): %s", e)


async def persist_chat_exchange(session_key: str, user_message: str, assistant_message: str) -> None:
    await append_transcript_turn(session_key, "user", user_message)
    await append_transcript_turn(session_key, "assistant", assistant_message)
