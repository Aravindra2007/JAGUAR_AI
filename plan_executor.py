"""Validation and dependency-aware execution for Jaguar task plans."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import task_state
from tool_executor import ToolExecutor, _validate_tool_input
from tools import TOOLS

MAX_PLAN_STEPS = 12


class PlanValidationError(ValueError):
    """Raised when a proposed plan is invalid or unsafe to execute."""


def validate_plan(
    plan: Any,
    allowed_tools: Optional[set] = None,
    max_steps: int = MAX_PLAN_STEPS,
) -> Dict[str, Any]:
    if not isinstance(plan, dict):
        raise PlanValidationError("A task plan must be a JSON object.")
    if set(plan) - {"goal", "steps", "response"}:
        raise PlanValidationError("The plan contains unexpected fields.")
    if not isinstance(plan.get("goal"), str) or not plan["goal"].strip():
        raise PlanValidationError("The plan must include a non-empty goal.")
    steps = plan.get("steps")
    if not isinstance(steps, list):
        raise PlanValidationError("Plan steps must be an array.")
    if len(steps) > max_steps:
        raise PlanValidationError(f"A plan cannot contain more than {max_steps} steps.")
    if "response" in plan and not isinstance(plan["response"], str):
        raise PlanValidationError("The plan response must be text.")

    permitted = allowed_tools if allowed_tools is not None else {
        tool["name"] for tool in TOOLS
    }
    ids = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"id", "tool", "input", "depends_on"}:
            raise PlanValidationError(
                "Each step must contain exactly id, tool, input, and depends_on."
            )
        step_id = step["id"]
        if not isinstance(step_id, str) or not step_id.strip() or len(step_id) > 64:
            raise PlanValidationError("Each step must have a valid ID.")
        if step_id in ids:
            raise PlanValidationError(f"Duplicate step ID: {step_id}.")
        ids.add(step_id)

    for step in steps:
        dependencies = step["depends_on"]
        if not isinstance(dependencies, list) or any(
            not isinstance(dependency, str) for dependency in dependencies
        ):
            raise PlanValidationError(f"Invalid dependencies for step {step['id']}.")
        if len(set(dependencies)) != len(dependencies):
            raise PlanValidationError(f"Duplicate dependencies for step {step['id']}.")
        unknown = set(dependencies) - ids
        if unknown:
            raise PlanValidationError(
                f"Step {step['id']} depends on unknown step(s): {', '.join(sorted(unknown))}."
            )
        if step["id"] in dependencies:
            raise PlanValidationError(f"Step {step['id']} cannot depend on itself.")
        tool_error = _validate_tool_input(
            step["tool"],
            step["input"],
            permitted,
        )
        if tool_error:
            raise PlanValidationError(f"Step {step['id']}: {tool_error}")

    remaining = {step["id"]: set(step["depends_on"]) for step in steps}
    completed = set()
    while remaining:
        ready = {
            step_id
            for step_id, dependencies in remaining.items()
            if dependencies <= completed
        }
        if not ready:
            raise PlanValidationError("Plan dependencies contain a cycle.")
        completed.update(ready)
        for step_id in ready:
            remaining.pop(step_id)

    normalized = {
        "goal": plan["goal"].strip(),
        "response": plan.get("response", "").strip(),
        "status": "pending",
        "steps": [],
    }
    for step in steps:
        normalized["steps"].append({
            "id": step["id"],
            "tool": step["tool"],
            "input": dict(step["input"]),
            "depends_on": list(step["depends_on"]),
            "status": "pending",
            "result": None,
            "observation": None,
        })
    return normalized


def execute_plan(
    plan: Any,
    executor: ToolExecutor,
    *,
    continuation: Optional[Dict[str, Any]] = None,
    max_steps: int = MAX_PLAN_STEPS,
) -> Dict[str, Any]:
    validated_plan = validate_plan(plan, executor.allowlist, max_steps=max_steps)
    if not validated_plan["steps"]:
        return {
            "kind": "result",
            "success": True,
            "text": validated_plan["response"] or validated_plan["goal"],
        }
    return _run_ready_steps(validated_plan, executor, continuation)


def resume_plan(
    token: str,
    decision: str,
    executor: ToolExecutor,
) -> Optional[Dict[str, Any]]:
    visible_pending = task_state.peek_pending_plan(token)
    if visible_pending is not None and (
        visible_pending.get("user_id", "") != executor.user_id
    ):
        return {
            "kind": "result",
            "success": False,
            "text": "That pending action is unavailable for this account.",
        }
    pending = task_state.pop_pending_plan(token)
    if pending is None:
        return None

    plan = pending["plan"]
    step = next(
        (item for item in plan["steps"] if item["id"] == pending["step_id"]),
        None,
    )
    confirmed = executor.execute_confirmed_result(token, decision)
    if step is None:
        return {"kind": "result", "success": False, "text": "The pending plan step was lost."}

    step["result"] = confirmed["text"]
    step["observation"] = confirmed.get("observation")
    step["status"] = _step_status(
        confirmed.get("observation"),
        confirmed["success"],
    )
    result = _run_ready_steps(plan, executor, pending.get("continuation"))
    if result.get("kind") == "result":
        result["continuation"] = pending.get("continuation")
    return result


def _run_ready_steps(
    plan: Dict[str, Any],
    executor: ToolExecutor,
    continuation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    by_id = {step["id"]: step for step in plan["steps"]}

    while True:
        for step in plan["steps"]:
            if step["status"] != "pending":
                continue
            if any(
                by_id[dependency]["status"] in {"failed", "blocked", "unverified"}
                for dependency in step["depends_on"]
            ):
                step["status"] = "blocked"
                step["result"] = "A prerequisite step failed."

        ready = [
            step
            for step in plan["steps"]
            if step["status"] == "pending"
            and all(by_id[dependency]["status"] == "completed" for dependency in step["depends_on"])
        ]
        if not ready:
            break

        for step in ready:
            step["status"] = "running"
            try:
                outcome = executor.execute(step["tool"], step["input"])
            except Exception as error:
                step["result"] = f"Tool execution failed: {error}"
                step["observation"] = {
                    "status": "failed",
                    "verified": False,
                    "failure_type": executor.observer.classify_failure(step["result"]),
                    "message": step["result"],
                }
                step["status"] = "failed"
                continue
            if outcome["kind"] == "confirmation":
                task_state.save_pending_plan(
                    outcome["token"],
                    plan,
                    step["id"],
                    continuation=continuation,
                )
                return {
                    "kind": "confirmation",
                    "type": "needs_confirmation",
                    "envelope": {
                        "token": outcome["token"],
                        "tool_name": outcome["tool_name"],
                        "tool_input": outcome["tool_input"],
                        "prompt": outcome["prompt"],
                    },
                }
            step["result"] = outcome["text"]
            step["observation"] = outcome.get("observation")
            step["status"] = _step_status(
                outcome.get("observation"),
                outcome.get("success", False),
            )

    return _report(plan)


def _step_status(observation: Optional[Dict[str, Any]], success: bool) -> str:
    if observation:
        status = observation.get("status", "failed")
        return "completed" if status == "verified" else status
    return "completed" if success else "failed"


def _report(plan: Dict[str, Any]) -> Dict[str, Any]:
    statuses = {step["status"] for step in plan["steps"]}
    success = statuses <= {"completed"}
    plan["status"] = "completed" if success else "failed"
    lines = [f"Task: {plan['goal']}"]
    for step in plan["steps"]:
        observation = step.get("observation")
        observed_message = observation.get("message") if observation else step["result"]
        lines.append(f"{step['id']} — {step['status']}: {observed_message or ''}")
    if success:
        lines.insert(1, "All steps completed.")
    elif "failed" in statuses or "blocked" in statuses or "unverified" in statuses:
        lines.insert(1, "The task was only partially completed.")
    else:
        lines.insert(1, "The task could not be completed.")
    return {
        "kind": "result",
        "success": success,
        "text": "\n".join(lines),
        "plan": plan,
    }
