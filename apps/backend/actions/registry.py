"""Action type registry: map action_type string -> handler."""
from __future__ import annotations

import logging
from typing import Any

from apps.backend.actions.api_call import ApiCallAction
from apps.backend.actions.base import BaseAction
from apps.backend.actions.transform import TransformAction
from apps.backend.actions.web_fetch import WebFetchAction
from apps.backend.db.models import Entry

logger = logging.getLogger(__name__)

REGISTRY: dict[str, type[BaseAction]] = {
    "web_fetch": WebFetchAction,
    "api_call": ApiCallAction,
    "transform": TransformAction,
}


def get_action(action_type: str) -> BaseAction | None:
    """Return action instance for type, or None if unknown."""
    cls = REGISTRY.get(action_type)
    return cls() if cls else None


async def run_action(action_type: str, params: dict[str, Any]) -> list[Entry]:
    """Execute action by type. Returns empty list if unknown or on error."""
    action = get_action(action_type)
    if not action:
        logger.warning("Unknown action_type: %s", action_type)
        return []
    try:
        return await action.execute(params)
    except Exception as e:
        logger.exception("Action %s failed: %s", action_type, e)
        return []
