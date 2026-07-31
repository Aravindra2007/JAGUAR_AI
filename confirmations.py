"""
Confirmation envelopes for tool-use.

When the Claude tool-use loop wants to perform a mutating action, the
tool executor does NOT execute it directly. Instead it returns a small
"needs_confirmation" envelope dict that the router forwards to whatever
UI surface asked. The user responds by Approve/Deny (Streamlit) or
yes/no (voice). The router then resolves the token back into the real
action via ToolExecutor.execute_confirmed.

Both UI surfaces key off `is_envelope(value)` so they can branch.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional


def build_envelope(tool_name: str, tool_input: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    """Wrap a pending action in the standard envelope shape."""
    return {
        "type": "needs_confirmation",
        "envelope": {
            "token": str(uuid.uuid4()),
            "tool_name": tool_name,
            "tool_input": dict(tool_input),
            "prompt": prompt,
        },
    }


def is_envelope(value: Any) -> bool:
    """True if a router return value is a confirmation envelope (not text)."""
    return isinstance(value, dict) and value.get("type") == "needs_confirmation"


def format_prompt(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Produce the human-readable prompt shown when the action needs approval.

    Keeps wording consistent across the Streamlit expander and the
    voice listener's TTS prompt.
    """
    if tool_name == "open_application":
        name = tool_input.get("name", "the app")
        return f"Open {name}?"
    if tool_name == "write_file":
        path = tool_input.get("path", "the file")
        content = tool_input.get("content", "")
        return f"Write {len(content)} characters to {path}?"
    if tool_name == "set_reminder":
        message = tool_input.get("message", "a reminder")
        return f"Set a reminder: '{message}'?"
    if tool_name == "run_shell_command":
        command = tool_input.get("command", "")
        return f"Run shell command '{command}'?"
    if tool_name == "close_app":
        return "Send Alt+F4 to the active window?"
    # Fallback for any future tool
    return f"Run tool '{tool_name}' with arguments {tool_input}?"


def confirmation_token(envelope: Dict[str, Any]) -> Optional[str]:
    """Convenience extractor for the token from an envelope dict."""
    if not is_envelope(envelope):
        return None
    return envelope["envelope"].get("token")
