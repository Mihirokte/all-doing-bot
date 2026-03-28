"""Administrative endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter

from apps.backend.pipeline.task_store import task_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


@router.post("/admin/clear-data")
async def clear_data() -> dict:
    """
    Clear past sessions and persisted cohort data.
    - Deletes all cohorts (and backing sheets in Google mode)
    - Clears in-memory task sessions
    """
    from apps.backend.db.catalogue import catalogue

    deleted_cohorts = 0
    cohorts = await catalogue.list_cohorts()
    for c in cohorts:
        try:
            await catalogue.delete_cohort(c.cohort_name)
            deleted_cohorts += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed deleting cohort %s: %s", c.cohort_name, e)

    cleared_tasks = task_store.clear_all()
    return {
        "status": "ok",
        "deleted_cohorts": deleted_cohorts,
        "cleared_tasks": cleared_tasks,
    }
