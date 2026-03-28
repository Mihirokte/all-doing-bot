"""Pydantic models for API request/response and task state."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueryAcceptResponse(BaseModel):
    """Response when a query is accepted."""

    task_id: str
    status: str = "accepted"
    session_key: str = "default"


class TaskResult(BaseModel):
    """Result payload when task completes (or error info when failed)."""

    cohort_name: Optional[str] = None
    entries_added: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None  # e.g. {"steps": [{"action": "...", "entry_count": N, "error": "..."}]}


class TaskStatusResponse(BaseModel):
    """Response for GET /status/<task_id>."""

    task_id: str
    status: str  # processing | completed | failed
    query: Optional[str] = None
    session_key: Optional[str] = None
    result: Optional["TaskResult"] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CohortInfo(BaseModel):
    """One cohort in the catalogue (for GET /cohorts)."""

    cohort_name: str
    cohort_description: str = ""
    action_type: str = ""
    sheet_name: str = ""
    entry_count: int = 0
    created_at: str = ""
    last_run: str = ""


class CohortEntry(BaseModel):
    """One entry in a cohort (for GET /cohort/<name>)."""

    entry_id: int
    content: str
    source: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


# --- Pipeline stage payloads (Parse → Plan → Execute → Store) ---


class ParsedIntent(BaseModel):
    """Output of Parse stage: cohort + action from user query."""

    cohort_name: str
    cohort_description: str = ""
    action_type: str = "web_fetch"
    action_params: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class PlanStep(BaseModel):
    """One step in the execution plan."""

    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class PlanOutput(BaseModel):
    """Output of Plan stage: list of steps."""

    steps: list[PlanStep] = Field(default_factory=list)  # list[] ok on 3.9


class ParseAndPlanOutput(BaseModel):
    """Combined parse+plan: intent and steps in one LLM call."""

    cohort_name: str
    cohort_description: str = ""
    action_type: str = "web_fetch"
    action_params: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    steps: list[PlanStep] = Field(default_factory=list)


class ParseResult(ParsedIntent):
    """Explicit parse-stage schema referenced in the planning docs."""


class PlanResult(PlanOutput):
    """Explicit plan-stage schema referenced in the planning docs."""


class SummarizeResult(BaseModel):
    """Output of summarize-stage extraction from web content."""

    title: str
    summary: str
    key_fields: Dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    """One memory item in short-term or long-term store."""

    memory_id: str
    session_key: str = "default"
    memory_type: str = "short_term"  # short_term | long_term
    role: str = "system"  # user | assistant | system
    content: str
    tags: list[str] = Field(default_factory=list)
    score: float = 1.0
    created_at: str


class MemoryHit(BaseModel):
    """Memory retrieval match details for diagnostics."""

    memory_id: str
    memory_type: str
    score: float = 0.0
    content: str


class MemoryContext(BaseModel):
    """Context injected into parse/plan from memory system."""

    short_term: list[MemoryRecord] = Field(default_factory=list)
    long_term: list[MemoryHit] = Field(default_factory=list)


class ChatWebRoute(BaseModel):
    """Binary routing for GET /chat: web retrieval vs direct answer, plus search query rewrite."""

    needs_web: bool = False
    ask_user_first: bool = False
    ask_user_message: str = ""
    search_query: str = ""


class WorkflowSaveBody(BaseModel):
    """POST body for deterministic task/note workflows."""

    text: str = ""
    session_key: str = "default"


class WorkflowItem(BaseModel):
    """One row in tasks or notes list."""

    entry_id: int = 0
    content: str = ""
    created_at: str = ""


class WorkflowSaveResponse(BaseModel):
    """Result of POST /workflows/task or /workflows/note."""

    ok: bool = True
    cohort_name: str = ""
    entry_id: Optional[int] = None
    message: str = ""
    error: Optional[str] = None
