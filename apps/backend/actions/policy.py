"""Policy and approval engine (MVP)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from apps.backend.config import settings


@dataclass
class PolicyDecision:
    decision: str  # allow | deny | require_approval
    reason: str
    requires_approval: bool = False


def _csv_set(raw: str) -> set[str]:
    return {part.strip().lower() for part in (raw or "").split(",") if part.strip()}


def _extract_hosts(params: dict[str, Any]) -> list[str]:
    urls = params.get("urls") or params.get("url") or []
    if isinstance(urls, str):
        urls = [urls]
    hosts: list[str] = []
    for item in urls:
        try:
            host = (urlparse(str(item)).hostname or "").strip().lower()
            if host:
                hosts.append(host)
        except Exception:
            continue
    return hosts


def evaluate_action_policy(action_type: str, params: dict[str, Any]) -> PolicyDecision:
    denied_actions = _csv_set(getattr(settings, "policy_deny_actions", ""))
    approval_actions = _csv_set(getattr(settings, "policy_require_approval_actions", ""))
    allowed_hosts = _csv_set(getattr(settings, "policy_allowed_hosts", ""))
    denied_hosts = _csv_set(getattr(settings, "policy_denied_hosts", ""))
    auto_approve = bool(getattr(settings, "policy_auto_approve", False))

    action_key = (action_type or "").strip().lower()
    if action_key in denied_actions:
        return PolicyDecision(decision="deny", reason=f"action '{action_key}' denied by policy")

    hosts = _extract_hosts(params)
    for host in hosts:
        if host in denied_hosts:
            return PolicyDecision(decision="deny", reason=f"host '{host}' denied by policy")
    if allowed_hosts and hosts:
        blocked = [host for host in hosts if host not in allowed_hosts]
        if blocked:
            return PolicyDecision(decision="deny", reason=f"hosts not in allowlist: {', '.join(blocked)}")

    if action_key in approval_actions:
        if auto_approve:
            return PolicyDecision(decision="allow", reason="auto-approval enabled", requires_approval=True)
        return PolicyDecision(decision="require_approval", reason=f"action '{action_key}' requires approval", requires_approval=True)

    return PolicyDecision(decision="allow", reason="policy passed")

