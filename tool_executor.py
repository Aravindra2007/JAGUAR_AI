"""
Tool executor for Jaguar AI's Claude tool-use loop.

The executor is the single place that decides whether a Claude-requested
tool action should run immediately, ask for user confirmation, or be
refused. The agent loop (`claude_tool_agent.run_claude_agent`) hands the
executor the `tool_use` blocks from each Anthropic response; the
executor returns either:

  - `{"kind": "result", "text": ..., "tool_use_id": "..."}`     -> safe to send back as a `tool_result` content block
  - `{"kind": "confirmation", "token": uuid, ...}`               -> needs user approval; stored in state for later resolution

The `execute_confirmed(token, decision)` method does the actual side
effect when the user approves, or returns "Cancelled." on deny.

Workspace path enforcement lives in tools._resolve_under_workspace,
not here. The executor just passes the configured workspace_dir into
each tool wrapper.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from commands import Commands
from confirmations import build_envelope, format_prompt
from tools import invoke_tool, run_confirmed
import state


class ToolExecutor:
    """Dispatches Anthropic `tool_use` blocks to the matching handler."""

    def __init__(
        self,
        workspace_dir: str = "",
        allowlist: Optional[set] = None,
        commands: Optional[Commands] = None,
    ):
        self.workspace_dir = workspace_dir or os.path.expanduser("~")
        self.allowlist = allowlist  # currently informational; tools.py enforces it
        self.commands = commands if commands is not None else Commands()

    # ------------------------------------------------------------------
    # Synchronous execution of a single tool_use block
    # ------------------------------------------------------------------

    def execute(self, tool_name: str, tool_input: Dict[str, Any], tool_use_id: str = "") -> Dict[str, Any]:
        """Run the wrapper for `tool_name` with the given input.

        Returns a dict shaped like either:
          {"kind": "result", "text": "...", "tool_use_id": "..."}
          {"kind": "confirmation", "token": "...", "prompt": "...", "tool_name": "...", "tool_input": {...}}
        """
        outcome = invoke_tool(tool_name, tool_input or {}, self.workspace_dir)

        if outcome.mutating:
            prompt = outcome.confirmation_prompt or format_prompt(tool_name, tool_input or {})
            envelope = build_envelope(tool_name, tool_input or {}, prompt)
            # Persist on the executor for execute_confirmed to find. We
            # also push to state so a UI surface can resolve the token
            # by querying the global state.
            state.push_pending_confirmation(envelope["envelope"]["token"], {
                "tool_name": tool_name,
                "tool_input": dict(tool_input or {}),
                "prompt": prompt,
            })
            return {"kind": "confirmation", **envelope["envelope"]}

        return {
            "kind": "result",
            "text": outcome.text,
            "tool_use_id": tool_use_id,
        }

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
            tool_input = getattr(block, "input", None) or (
                block.get("input") if isinstance(block, dict) else {}
            )
            tool_use_id = getattr(block, "id", None) or (
                block.get("id") if isinstance(block, dict) else ""
            )

            outcome = self.execute(tool_name, tool_input or {}, tool_use_id=tool_use_id)

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
                "content": outcome["text"],
            })

        return results, pending_envelope

    # ------------------------------------------------------------------
    # Resolve a pending confirmation
    # ------------------------------------------------------------------

    def execute_confirmed(self, token: str, decision: str) -> str:
        """Run (or cancel) the action the user approved/denied."""
        pending = state.pop_pending_confirmation(token)
        if pending is None:
            return "That action has expired or was already handled."

        if (decision or "").strip().lower() not in {"yes", "y", "true", "approve"}:
            return "Cancelled."

        cfg = state.get_llm_config()
        reminders_path = cfg.get("reminders_path", "reminders.json")
        return run_confirmed(
            tool_name=pending["tool_name"],
            tool_input=pending["tool_input"],
            workspace_dir=self.workspace_dir,
            reminders_path=reminders_path,
        )
