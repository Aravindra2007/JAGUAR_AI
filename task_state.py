"""In-memory continuation state for plans paused at user approval."""

from __future__ import annotations

import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Dict, Optional

_lock = threading.Lock()
_pending_plans: Dict[str, Dict[str, Any]] = {}


def save_pending_plan(
    token: str,
    plan: Dict[str, Any],
    step_id: str,
    continuation: Optional[Dict[str, Any]] = None,
) -> None:
    continuation_state = deepcopy(continuation) if continuation is not None else {}
    task_id = continuation_state.get("task_id") or str(uuid.uuid4())
    completed_steps = list(continuation_state.get("completed_steps", []))
    completed_steps.extend(
        step["id"]
        for step in plan.get("steps", [])
        if step.get("status") == "completed" and step["id"] not in completed_steps
    )
    observations = list(continuation_state.get("observations", []))
    observations.extend(
        step["observation"]
        for step in plan.get("steps", [])
        if step.get("observation") is not None
        and step["observation"] not in observations
    )
    continuation_state.update({
        "task_id": task_id,
        "completed_steps": completed_steps,
        "observations": observations,
    })
    with _lock:
        now = time.time()
        expired = [
            pending_token
            for pending_token, pending in _pending_plans.items()
            if pending["expires_at"] <= now
        ]
        for pending_token in expired:
            _pending_plans.pop(pending_token, None)
        _pending_plans[token] = {
            "task_id": task_id,
            "user_id": str(continuation_state.get("user_id") or ""),
            "goal": plan.get("goal", ""),
            "status": "awaiting_confirmation",
            "current_step": step_id,
            "completed_steps": completed_steps,
            "observations": observations,
            "plan": deepcopy(plan),
            "step_id": step_id,
            "continuation": continuation_state,
            "expires_at": now + 300,
        }


def pop_pending_plan(token: str) -> Optional[Dict[str, Any]]:
    with _lock:
        pending = _pending_plans.pop(token, None)
        if pending is None or pending["expires_at"] <= time.time():
            return None
        return pending


def peek_pending_plan(token: str) -> Optional[Dict[str, Any]]:
    with _lock:
        pending = _pending_plans.get(token)
        if pending is None:
            return None
        if pending["expires_at"] <= time.time():
            _pending_plans.pop(token, None)
            return None
        return deepcopy(pending)
