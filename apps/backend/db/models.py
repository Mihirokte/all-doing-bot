"""DB record schemas: Cohort (catalogue row), Entry (cohort row)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Cohort(BaseModel):
    """One row in the _catalogue sheet."""

    cohort_name: str
    cohort_description: str = ""
    action_type: str = "web_fetch"
    action_params: str = "{}"  # JSON string
    created_at: str = ""
    last_run: str = ""
    sheet_name: str = ""
    entry_count: int = 0


class Entry(BaseModel):
    """One row in a cohort's data sheet."""

    entry_id: int = 0
    content: str
    source: str = ""
    metadata: str = "{}"  # JSON string
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
