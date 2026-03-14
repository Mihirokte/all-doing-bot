"""Context vars for run_id and step_index correlation."""
from __future__ import annotations

from contextvars import ContextVar

run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
step_index_var: ContextVar[int | None] = ContextVar("step_index", default=None)


def get_run_id() -> str | None:
    return run_id_var.get()


def get_step_index() -> int | None:
    return step_index_var.get()


def set_run_context(run_id: str | None, step_index: int | None = None) -> None:
    run_id_var.set(run_id)
    step_index_var.set(step_index)
