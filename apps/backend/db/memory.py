"""Session and long-term memory store (MVP)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.backend.models.schemas import MemoryContext, MemoryHit, MemoryRecord


class MemoryStore:
    """In-memory memory store with short-term window and long-term retrieval."""

    def __init__(self) -> None:
        self._short_term: dict[str, list[MemoryRecord]] = {}
        self._long_term: list[MemoryRecord] = []

    async def append_short_term(self, session_key: str, role: str, content: str, tags: list[str] | None = None) -> MemoryRecord:
        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            session_key=(session_key or "default").strip() or "default",
            memory_type="short_term",
            role=role,
            content=content.strip(),
            tags=tags or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._short_term.setdefault(record.session_key, []).append(record)
        self._short_term[record.session_key] = self._short_term[record.session_key][-50:]
        return record

    async def get_short_term_window(self, session_key: str, limit: int = 8) -> list[MemoryRecord]:
        key = (session_key or "default").strip() or "default"
        return list(self._short_term.get(key, [])[-max(1, limit):])

    async def upsert_long_term(
        self,
        session_key: str,
        content: str,
        tags: list[str] | None = None,
        score: float = 1.0,
    ) -> MemoryRecord:
        key = (session_key or "default").strip() or "default"
        normalized = " ".join((content or "").lower().split())
        for idx, existing in enumerate(self._long_term):
            if existing.session_key == key and " ".join(existing.content.lower().split()) == normalized:
                updated = MemoryRecord(
                    memory_id=existing.memory_id,
                    session_key=key,
                    memory_type="long_term",
                    role="system",
                    content=content.strip(),
                    tags=tags or existing.tags,
                    score=max(existing.score, score),
                    created_at=existing.created_at,
                )
                self._long_term[idx] = updated
                return updated
        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            session_key=key,
            memory_type="long_term",
            role="system",
            content=content.strip(),
            tags=tags or [],
            score=score,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._long_term.append(record)
        self._long_term = self._long_term[-500:]
        return record

    async def search_long_term(self, session_key: str, query: str, limit: int = 5) -> list[MemoryHit]:
        key = (session_key or "default").strip() or "default"
        terms = {part for part in (query or "").lower().split() if len(part) > 2}
        hits: list[MemoryHit] = []
        if not terms:
            return hits
        for record in reversed(self._long_term):
            if record.session_key != key:
                continue
            text = record.content.lower()
            overlap = sum(1 for term in terms if term in text)
            if overlap <= 0:
                continue
            score = float(overlap) + float(record.score)
            hits.append(
                MemoryHit(
                    memory_id=record.memory_id,
                    memory_type="long_term",
                    score=score,
                    content=record.content,
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: max(1, limit)]

    async def get_context(self, session_key: str, query: str) -> MemoryContext:
        short_term = await self.get_short_term_window(session_key)
        long_term = await self.search_long_term(session_key, query)
        return MemoryContext(short_term=short_term, long_term=long_term)


memory_store = MemoryStore()

