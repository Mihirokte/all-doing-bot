"""Short-query chat endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.backend.services.chat_service import ChatLLMUnavailableError, handle_chat

router = APIRouter(tags=["chat"])


@router.get("/chat")
async def chat(q: str = "", session_key: str = "default") -> dict[str, str]:
    """
    Short-query path: session-scoped transcript (Sheets + memory), structured gate, web vs direct.
    Frontend should pass session_key (same as workflows) so follow-ups resolve entities.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if len(q) > 10000:
        raise HTTPException(status_code=400, detail="Query too long (max 10000 characters)")
    try:
        return await handle_chat(q.strip(), session_key)
    except ChatLLMUnavailableError:
        raise HTTPException(status_code=503, detail="LLM unavailable for chat") from None
