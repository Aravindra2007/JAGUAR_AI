"""
Tool executor for Jaguar AI's allowlisted tool-use flow.

The executor is the single place that validates tool requests and decides
whether an action should run immediately, ask for confirmation, or be
refused. Both the planner and provider-specific tool loops use this layer.
The executor returns either:

  - `{"kind": "result", "text": ..., "tool_use_id": "..."}`     -> safe to send back as a `tool_result` content block
  - `{"kind": "confirmation", "token": uuid, ...}`               -> needs user approval; stored in state for later resolution

The `execute_confirmed(token, decision)` method does the actual side
effect when the user approves, or returns "Cancelled." on deny.

Workspace path enforcement lives in tools._resolve_under_workspace,
not here. The executor just passes the configured workspace_dir into
each tool wrapper.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from commands import Commands
from confirmations import build_envelope, format_prompt
from observer import ObservationEngine
from tools import TOOLS, _resolve_under_workspace, invoke_tool, run_confirmed
import state

CONFIRMATION_TTL_SECONDS = 300


def _validate_tool_input(
    tool_name: str,
    tool_input: Any,
    allowed_tools: set,
) -> Optional[str]:
    if not isinstance(tool_name, str) or tool_name not in allowed_tools:
        return f"Tool '{tool_name}' is not allowed."
    if not isinstance(tool_input, dict):
        return "Tool input must be an object."
    if any(not isinstance(key, str) for key in tool_input):
        return "Tool input keys must be strings."

    schema = next(
        (tool["input_schema"] for tool in TOOLS if tool["name"] == tool_name),
        None,
    )
    if schema is None:
        return f"Tool '{tool_name}' is not allowed."
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    missing = [key for key in required if key not in tool_input]
    if missing:
        return f"Missing required tool input: {', '.join(missing)}."

    unexpected = [key for key in tool_input if key not in properties]
    if unexpected:
        return f"Unexpected tool input: {', '.join(sorted(unexpected))}."

    python_types = {
        "string": str,
        "object": dict,
        "array": list,
        "boolean": bool,
        "integer": int,
        "number": (int, float),
    }
    for key, value in tool_input.items():
        expected = properties[key].get("type")
        expected_type = python_types.get(expected)
        if expected_type is not None:
            if not isinstance(value, expected_type) or (
                expected in {"integer", "number"} and isinstance(value, bool)
            ):
                return f"Tool input '{key}' must be {expected}."

    return None


class ToolExecutor:
    """Dispatches model tool requests to the matching handler."""

    def __init__(
        self,
        workspace_dir: str = "",
        allowlist: Optional[set] = None,
        commands: Optional[Commands] = None,
        user_id: Optional[str] = None,
    ):
        self.workspace_dir = os.path.expanduser(workspace_dir or "~")
        self.user_id = str(user_id or state.get_current_user_id() or "")
        self.allowlist = set(allowlist) if allowlist is not None else {
            tool["name"] for tool in TOOLS
        }
        self.commands = commands if commands is not None else Commands()
        self.observer = ObservationEngine(
            self.workspace_dir,
            user_id=self.user_id,
        )

    # ------------------------------------------------------------------
    # Synchronous execution of a single tool_use block
    # ------------------------------------------------------------------

    def execute(self, tool_name: str, tool_input: Dict[str, Any], tool_use_id: str = "") -> Dict[str, Any]:
        """Run the wrapper for `tool_name` with the given input.

        Returns a dict shaped like either:
          {"kind": "result", "text": "...", "tool_use_id": "..."}
          {"kind": "confirmation", "token": "...", "prompt": "...", "tool_name": "...", "tool_input": {...}}
        """
        validation_error = _validate_tool_input(
            tool_name,
            tool_input,
            self.allowlist,
        )
        if validation_error:
            observation = self.observer.verify(
                tool_name if isinstance(tool_name, str) else "",
                tool_input if isinstance(tool_input, dict) else {},
                {"success": False, "text": validation_error},
            )
            return {
                "kind": "result",
                "text": validation_error,
                "success": False,
                "observation": observation,
                "tool_use_id": tool_use_id,
            }

        outcome = invoke_tool(tool_name, tool_input, self.workspace_dir)

        if outcome.mutating:
            if self._has_document_directory_approval(tool_name, tool_input):
                try:
                    execution_result = run_confirmed(
                        tool_name=tool_name,
                        tool_input=tool_input,
                        workspace_dir=self.workspace_dir,
                        user_id=self.user_id,
                    )
                except Exception as error:
                    execution_result = {
                        "success": False,
                        "text": f"Tool execution failed: {error}",
                    }
                observation = self.observer.verify(
                    tool_name,
                    tool_input,
                    execution_result,
                )
                return {
                    "kind": "result",
                    "text": execution_result.get("text", observation["message"]),
                    "success": observation["verified"],
                    "observation": observation,
                    "tool_use_id": tool_use_id,
                }

            prompt = outcome.confirmation_prompt or format_prompt(tool_name, tool_input)
            envelope = build_envelope(tool_name, tool_input, prompt)
            # Persist on the executor for execute_confirmed to find. We
            # also push to state so a UI surface can resolve the token
            # by querying the global state.
            state.push_pending_confirmation(envelope["envelope"]["token"], {
                "tool_name": tool_name,
                "tool_input": dict(tool_input),
                "prompt": prompt,
                "expires_at": time.time() + CONFIRMATION_TTL_SECONDS,
                "user_id": self.user_id,
            })
            return {"kind": "confirmation", **envelope["envelope"]}

        observation = self.observer.verify(
            tool_name,
            tool_input,
            {"success": outcome.success, "text": outcome.text},
        )
        return {
            "kind": "result",
            "text": outcome.text,
            "success": observation["verified"],
            "observation": observation,
            "tool_use_id": tool_use_id,
        }

    def _has_document_directory_approval(self, tool_name, tool_input):
        if tool_name != "write_file":
            return False
        try:
            path = _resolve_under_workspace(
                self.workspace_dir,
                tool_input.get("path", ""),
            )
        except ValueError:
            return False
        return state.has_document_directory_approval(
            self.user_id,
            self.workspace_dir,
            os.path.dirname(path),
        )

    # ------------------------------------------------------------------
    # Walk a response.content list
    # ------------------------------------------------------------------

    def execute_many(
        self, blocks: List[Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Run every tool_use block in `blocks`.

        Returns (tool_result_content_blocks, confirmation_envelope_or_None).
        If any block requires confirmation, the agent loop should bail
        out with the envelope instead of looping further.
        """
        results: List[Dict[str, Any]] = []
        pending_envelope: Optional[Dict[str, Any]] = None

        for block in blocks:
            # Anthropic SDK returns blocks with `.type` attribute; but
            # plain dicts also work (e.g. in tests). Handle both.
            block_type = getattr(block, "type", None) or (
                block.get("type") if isinstance(block, dict) else None
            )

            if block_type != "tool_use":
                continue

            tool_name = getattr(block, "name", None) or (
                block.get("name") if isinstance(block, dict) else ""
            )
            tool_input = getattr(block, "input", None)
            if tool_input is None and isinstance(block, dict):
                tool_input = block.get("input")
            tool_use_id = getattr(block, "id", None) or (
                block.get("id") if isinstance(block, dict) else ""
            )

            outcome = self.execute(tool_name, tool_input, tool_use_id=tool_use_id)

            if outcome["kind"] == "confirmation":
                pending_envelope = {
                    "type": "needs_confirmation",
                    "envelope": {
                        "token": outcome["token"],
                        "tool_name": outcome["tool_name"],
                        "tool_input": outcome["tool_input"],
                        "prompt": outcome["prompt"],
                    },
                }
                # Stop at the first confirmation request.
                break

            # Anthropic Messages API: tool_result blocks look like
            #     {"type": "tool_result", "tool_use_id": "...", "content": "..."}
            # We pass the textual result straight back.
            results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": json.dumps(
                    {
                        "success": outcome["success"],
                        "text": outcome["text"],
                        "observation": outcome["observation"],
                    },
                    ensure_ascii=True,
                ),
            })

        return results, pending_envelope

    # ------------------------------------------------------------------
    # Resolve a pending confirmation
    # ------------------------------------------------------------------

    def execute_confirmed(self, token: str, decision: str) -> str:
        """Run (or cancel) the action the user approved/denied."""
        return self.execute_confirmed_result(token, decision)["text"]

    def execute_confirmed_result(self, token: str, decision: str) -> Dict[str, Any]:
        """Resolve approval and return an explicit success flag for plans."""
        pending, expired = state.take_pending_confirmation(
            token,
            user_id=self.user_id,
        )
        if expired:
            return {
                "success": False,
                "text": "Confirmation expired. Please request the action again.",
                "observation": {
                    "status": "failed",
                    "verified": False,
                    "failure_type": "needs_user_input",
                    "message": "Confirmation expired. Please request the action again.",
                },
            }
        if pending is None:
            return {
                "success": False,
                "text": "That action has expired or was already handled.",
                "observation": {
                    "status": "failed",
                    "verified": False,
                    "failure_type": "needs_user_input",
                    "message": "That action has expired or was already handled.",
                },
            }

        if (decision or "").strip().lower() not in {"yes", "y", "true", "approve"}:
            observation = {
                "status": "failed",
                "verified": False,
                "failure_type": "needs_user_input",
                "message": "Cancelled.",
            }
            return {"success": False, "text": "Cancelled.", "observation": observation}

        validation_error = _validate_tool_input(
            pending.get("tool_name"),
            pending.get("tool_input"),
            self.allowlist,
        )
        if validation_error:
            observation = self.observer.verify(
                pending.get("tool_name", ""),
                pending.get("tool_input", {}),
                {"success": False, "text": validation_error},
            )
            return {
                "success": False,
                "text": validation_error,
                "observation": observation,
            }

        current_outcome = invoke_tool(
            pending["tool_name"],
            pending["tool_input"],
            self.workspace_dir,
        )
        if not current_outcome.mutating:
            observation = self.observer.verify(
                pending["tool_name"],
                pending["tool_input"],
                {
                    "success": current_outcome.success,
                    "text": current_outcome.text,
                },
            )
            return {
                "success": observation["verified"],
                "text": current_outcome.text,
                "observation": observation,
            }

        try:
            execution_result = run_confirmed(
                tool_name=pending["tool_name"],
                tool_input=pending["tool_input"],
                workspace_dir=self.workspace_dir,
                user_id=self.user_id,
            )
        except Exception as error:
            execution_result = {
                "success": False,
                "text": f"Tool execution failed: {error}",
            }
        observer = ObservationEngine(self.workspace_dir, user_id=self.user_id)
        observation = observer.verify(
            pending["tool_name"],
            pending["tool_input"],
            execution_result,
        )
        if (
            pending["tool_name"] == "write_file"
            and observation.get("verified")
        ):
            approved_path = _resolve_under_workspace(
                self.workspace_dir,
                pending["tool_input"]["path"],
            )
            state.remember_document_directory_approval(
                self.user_id,
                self.workspace_dir,
                os.path.dirname(approved_path),
            )
        return {
            "success": observation["verified"],
            "text": execution_result.get("text", observation["message"]),
            "observation": observation,
        }
