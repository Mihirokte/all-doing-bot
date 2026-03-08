"""Data transform action: normalize input payloads into Entry rows."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.backend.actions.base import BaseAction
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return json.dumps(str(obj))


class TransformAction(BaseAction):
    """Turn structured input (list/dict) into normalized Entry rows."""

    async def execute(self, params: dict[str, Any]) -> list[Entry]:
        data = params.get("input") or params.get("data")
        if data is None:
            raise ValueError("transform requires 'input' or 'data' in action_params")
        content_field = params.get("field") or params.get("content_key")
        now = datetime.now(timezone.utc).isoformat()
        entries: list[Entry] = []

        if isinstance(data, list):
            for i, item in enumerate(data[:500]):
                if content_field and isinstance(item, dict) and content_field in item:
                    content = str(item[content_field])
                else:
                    content = _safe_json_dumps(item) if not isinstance(item, str) else item
                entries.append(
                    Entry(
                        content=content,
                        source=params.get("source") or "transform",
                        metadata=_safe_json_dumps({"index": i, "params": {k: v for k, v in params.items() if k not in ("input", "data", "field", "content_key")}}),
                        created_at=now,
                    )
                )
            return entries

        if isinstance(data, dict):
            if content_field and content_field in data:
                content = str(data[content_field])
            else:
                content = _safe_json_dumps(data)
            entries.append(
                Entry(
                    content=content,
                    source=params.get("source") or "transform",
                    metadata=_safe_json_dumps({k: v for k, v in params.items() if k not in ("input", "data", "field", "content_key")}),
                    created_at=now,
                )
            )
            return entries

        entries.append(
            Entry(
                content=str(data),
                source=params.get("source") or "transform",
                metadata=_safe_json_dumps({"params": params}),
                created_at=now,
            )
        )
        return entries
