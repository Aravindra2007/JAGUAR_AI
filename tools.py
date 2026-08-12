"""
Jaguar AI — Phase 1 tool catalog.

Each tool wrapper takes its declared input and returns a `ToolOutcome`
namedtuple with:
    text                 - what the model will see as the tool result
    mutating             - whether the action changes state on the user's PC
    confirmation_prompt  - the one-line human sentence to read/display
                           when asking for permission (None for read-only)

The wrappers themselves do NOT trigger any side effect. They classify
the action and (for mutating ones) return `mutating=True` so the
executor will swap in a confirmation envelope. The actual side effect
runs in ToolExecutor.execute_confirmed only after the user approves.

This split keeps the model loop in claude_tool_agent.py simple: it
just calls executor.execute(name, input) and gets back either a
finished result or an envelope. No tools here should ever call
subprocess / os.system / webbrowser / pyautogui directly — those
happen only inside execute_confirmed.
"""

from __future__ import annotations

import json
import os
import re
import time
import webbrowser
from collections import namedtuple
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------
# Outcome + constants
# ---------------------------------

ToolOutcome = namedtuple("ToolOutcome", "text mutating confirmation_prompt")


SHELL_ALLOWLIST = {
    "dir", "ls", "whoami", "date", "time",
    "tasklist", "systeminfo", "where", "pwd",
    "hostname", "ipconfig", "echo",
    "notepad", "calc", "mspaint", "code",
}

# Friendly aliases -> real executable names. Mirrors the keyword
# command table in commands.py so the LLM and the keyword router
# both target the same launchers.
APP_ALIASES = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "vscode": "code",
    "code": "code",
    "vs code": "code",
    "command prompt": "cmd",
    "cmd": "cmd",
    "file explorer": "explorer",
    "explorer": "explorer",
    "chrome": "chrome",
    "google chrome": "chrome",
}

WEBSITE_ALLOWLIST = {
    "google": "https://google.com",
    "youtube": "https://youtube.com",
    "github": "https://github.com",
    "chatgpt": "https://chat.openai.com",
    "stack overflow": "https://stackoverflow.com",
    "wikipedia": "https://wikipedia.org",
}

WORKSPACE_MAX_READ_CHARS = 8000
SHELL_OUTPUT_MAX_CHARS = 4000

# Only allow shell commands composed of these characters. Blocks
# metacharacters (& | ; > < ` $ ( ) * ? etc.) even if the head token
# is on the allowlist, so `dir & del foo.txt` is rejected.
_SAFE_SHELL_RX = re.compile(r"^[A-Za-z0-9 _./:\\-]+$")


# ---------------------------------
# Helpers
# ---------------------------------

def _resolve_under_workspace(workspace_dir: str, path: str) -> str:
    """Resolve `path` (absolute or relative) into an absolute path and
    confirm it stays under `workspace_dir`. Returns the absolute path.

    Raises ValueError if the resolved path escapes the workspace.
    """
    workspace_abs = os.path.abspath(workspace_dir)

    if os.path.isabs(path):
        candidate = os.path.abspath(path)
    else:
        candidate = os.path.abspath(os.path.join(workspace_abs, path))

    try:
        common = os.path.commonpath([candidate, workspace_abs])
    except ValueError:
        # Different drives on Windows, etc.
        raise ValueError("Path is outside the workspace.")

    if common != workspace_abs:
        raise ValueError("Path is outside the workspace.")

    return candidate


def _format_dir_listing(workspace_dir: str, abs_path: str) -> str:
    """Render an os.scandir listing as a small text table."""
    rows = [("Name", "Type", "Size", "Modified")]
    with os.scandir(abs_path) as it:
        for entry in it:
            try:
                stat = entry.stat(follow_symlinks=False)
                size = stat.st_size
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                size = "?"
                modified = "?"
            entry_type = "dir" if entry.is_dir(follow_symlinks=False) else "file"
            rows.append((entry.name, entry_type, str(size), modified))

    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    lines = []
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    header = f"Directory listing of {abs_path} (workspace: {workspace_dir}):"
    return header + "\n" + "\n".join(lines)


# ---------------------------------
# Tool wrappers
# ---------------------------------

def open_application(name: str, workspace_dir: str = "") -> ToolOutcome:
    """Launch a desktop application by friendly alias."""
    key = (name or "").strip().lower()
    if key not in APP_ALIASES:
        return ToolOutcome(
            text=f"I don't know how to open '{name}'. Try one of: {', '.join(sorted(APP_ALIASES))}.",
            mutating=False,
            confirmation_prompt=None,
        )
    return ToolOutcome(
        text=f"Will launch {APP_ALIASES[key]}.",
        mutating=True,
        confirmation_prompt=f"Open {key}?",
    )


def open_website(url_or_alias: str, workspace_dir: str = "") -> ToolOutcome:
    """Open a website by alias (must be on WEBSITE_ALLOWLIST)."""
    key = (url_or_alias or "").strip().lower()
    if key in WEBSITE_ALLOWLIST:
        return ToolOutcome(
            text=f"Opening {WEBSITE_ALLOWLIST[key]}.",
            mutating=False,
            confirmation_prompt=None,
        )
    return ToolOutcome(
        text=(
            "That site isn't on the allowlist. Allowed: "
            + ", ".join(sorted(WEBSITE_ALLOWLIST)) + "."
        ),
        mutating=False,
        confirmation_prompt=None,
    )


def list_directory(path: str, workspace_dir: str) -> ToolOutcome:
    """Read-only: list a directory under the workspace."""
    if not workspace_dir:
        return ToolOutcome(
            text="No workspace folder is configured.",
            mutating=False,
            confirmation_prompt=None,
        )
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path or ".")
    except ValueError as e:
        return ToolOutcome(text=str(e), mutating=False, confirmation_prompt=None)

    if not os.path.isdir(abs_path):
        return ToolOutcome(
            text=f"{abs_path} is not a directory.",
            mutating=False,
            confirmation_prompt=None,
        )

    return ToolOutcome(
        text=_format_dir_listing(workspace_dir, abs_path),
        mutating=False,
        confirmation_prompt=None,
    )


def read_file(path: str, workspace_dir: str) -> ToolOutcome:
    """Read-only: read a text file under the workspace (truncated)."""
    if not workspace_dir:
        return ToolOutcome(
            text="No workspace folder is configured.",
            mutating=False,
            confirmation_prompt=None,
        )
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path)
    except ValueError as e:
        return ToolOutcome(text=str(e), mutating=False, confirmation_prompt=None)

    if not os.path.isfile(abs_path):
        return ToolOutcome(
            text=f"{abs_path} is not a file.",
            mutating=False,
            confirmation_prompt=None,
        )

    with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read(WORKSPACE_MAX_READ_CHARS)

    if len(content) == WORKSPACE_MAX_READ_CHARS:
        content += "\n\n[...truncated]"

    return ToolOutcome(text=content, mutating=False, confirmation_prompt=None)


def write_file(path: str, content: str, workspace_dir: str) -> ToolOutcome:
    """Mutating: write text content to a file under the workspace."""
    if not workspace_dir:
        return ToolOutcome(
            text="No workspace folder is configured.",
            mutating=False,
            confirmation_prompt=None,
        )
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path)
    except ValueError as e:
        return ToolOutcome(text=str(e), mutating=False, confirmation_prompt=None)

    return ToolOutcome(
        text=f"Will write {len(content or '')} characters to {abs_path}.",
        mutating=True,
        confirmation_prompt=f"Write {len(content or '')} characters to {abs_path}?",
    )


def set_reminder(message: str, fire_at_iso: str, workspace_dir: str = "") -> ToolOutcome:
    """Mutating: append a reminder to reminders.json. Phase 1 only writes
    the file — actually firing the reminder is Phase 2."""
    message = (message or "").strip()
    if not message:
        return ToolOutcome(
            text="Reminder message cannot be empty.",
            mutating=False,
            confirmation_prompt=None,
        )
    try:
        fire_at = datetime.fromisoformat(fire_at_iso)
    except (TypeError, ValueError):
        return ToolOutcome(
            text=f"'{fire_at_iso}' is not a valid ISO timestamp.",
            mutating=False,
            confirmation_prompt=None,
        )

    seconds_until = (fire_at - datetime.now()).total_seconds()
    if seconds_until < 60:
        confirm_prompt = f"Reminder fires in {int(seconds_until)} seconds. Confirm?"
    else:
        confirm_prompt = f"Set reminder for {fire_at.strftime('%Y-%m-%d %H:%M')}?"

    return ToolOutcome(
        text=f"Will save reminder '{message}' for {fire_at.isoformat()}.",
        mutating=True,
        confirmation_prompt=confirm_prompt,
    )


def run_shell_command(command: str, workspace_dir: str = "") -> ToolOutcome:
    """Mutating: run a shell command if its head token is on the allowlist
    and the command string contains only safe characters."""
    command = (command or "").strip()
    if not command:
        return ToolOutcome(
            text="Empty shell command.",
            mutating=False,
            confirmation_prompt=None,
        )

    if not _SAFE_SHELL_RX.match(command):
        return ToolOutcome(
            text="command not in allowlist, please run it manually.",
            mutating=False,
            confirmation_prompt=None,
        )

    head = command.split(maxsplit=1)[0].lower()
    if head not in SHELL_ALLOWLIST:
        return ToolOutcome(
            text="command not in allowlist, please run it manually.",
            mutating=False,
            confirmation_prompt=None,
        )

    return ToolOutcome(
        text=f"Will run shell command '{command}'.",
        mutating=True,
        confirmation_prompt=f"Run shell command '{command}'?",
    )


def close_app(workspace_dir: str = "") -> ToolOutcome:
    """Mutating: send Alt+F4 to the active window (via pyautogui)."""
    return ToolOutcome(
        text="Will send Alt+F4 to the active window.",
        mutating=True,
        confirmation_prompt="Send Alt+F4 to the active window?",
    )


# ---------------------------------
# Tool catalog (Anthropic Messages API format)
# ---------------------------------

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "open_application",
        "description": (
            "Launch a desktop application on the user's Windows PC by a "
            "friendly name. Allowed apps: notepad, calculator, paint, "
            "vscode, command prompt, file explorer, chrome. Requires user "
            "confirmation before launching."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Friendly name of the application to launch.",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "open_website",
        "description": (
            "Open a website in the user's default browser by an alias from "
            "the allowlist: google, youtube, github, chatgpt, stack overflow, "
            "wikipedia. Reading-only from the user's perspective."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url_or_alias": {
                    "type": "string",
                    "description": "Friendly name of the website to open.",
                }
            },
            "required": ["url_or_alias"],
        },
    },
    {
        "name": "list_directory",
        "description": (
            "List files and subdirectories inside the configured workspace "
            "folder. The path must be inside the workspace; attempts to "
            "escape it (e.g. '../', absolute paths elsewhere) are refused."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to the workspace, or '.' for the workspace root.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a text file under the workspace. Truncated to 8000 characters. "
            "Refuses paths outside the workspace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (absolute or relative to the workspace).",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file under the workspace. Refuses paths "
            "outside the workspace. Requires user confirmation before writing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (absolute or relative to the workspace).",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "set_reminder",
        "description": (
            "Save a reminder message and the time it should fire (ISO 8601 "
            "timestamp, e.g. '2026-07-27T15:30:00'). Phase 1 only persists "
            "the reminder; firing is Phase 2. Requires user confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "What the reminder should say.",
                },
                "fire_at_iso": {
                    "type": "string",
                    "description": "ISO 8601 datetime when the reminder should fire.",
                },
            },
            "required": ["message", "fire_at_iso"],
        },
    },
    {
        "name": "run_shell_command",
        "description": (
            "Run a shell command on the user's PC. The first token must be "
            "on a fixed allowlist (dir, ls, whoami, date, time, tasklist, "
            "systeminfo, where, pwd, hostname, ipconfig, echo, notepad, "
            "calc, mspaint, code) and the full command must use only "
            "alphanumerics, spaces, dots, slashes, backslashes, colons, "
            "dashes, and underscores. Any other command is refused with "
            "the literal text 'command not in allowlist, please run it "
            "manually.'. Requires user confirmation before running."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run.",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "close_app",
        "description": (
            "Send Alt+F4 to the currently focused window. Requires user "
            "confirmation before executing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ---------------------------------
# Dispatch table for the executor
# ---------------------------------
# Maps tool name -> callable returning a ToolOutcome. Each callable
# takes (tool_input: dict, workspace_dir: str).

def _invoke(tool_name: str, tool_input: Dict[str, Any], workspace_dir: str) -> ToolOutcome:
    handlers = {
        "open_application":   lambda i: open_application(i.get("name", ""), workspace_dir),
        "open_website":      lambda i: open_website(i.get("url_or_alias", ""), workspace_dir),
        "list_directory":    lambda i: list_directory(i.get("path", "."), workspace_dir),
        "read_file":         lambda i: read_file(i.get("path", ""), workspace_dir),
        "write_file":        lambda i: write_file(i.get("path", ""), i.get("content", ""), workspace_dir),
        "set_reminder":      lambda i: set_reminder(i.get("message", ""), i.get("fire_at_iso", ""), workspace_dir),
        "run_shell_command": lambda i: run_shell_command(i.get("command", ""), workspace_dir),
        "close_app":         lambda i: close_app(workspace_dir),
    }
    handler = handlers.get(tool_name)
    if handler is None:
        return ToolOutcome(
            text=f"Unknown tool: {tool_name}",
            mutating=False,
            confirmation_prompt=None,
        )
    return handler(tool_input)


# ---------------------------------
# Side-effect runners (called only after user confirms)
# ---------------------------------

def run_confirmed(tool_name: str, tool_input: Dict[str, Any], workspace_dir: str,
                   reminders_path: str = "reminders.json") -> str:
    """Perform the actual side effect of a tool the user has approved.

    `tool_input` MUST be the same dict that was passed when generating
    the confirmation envelope. `workspace_dir` and `reminders_path` come
    from state. Returns the human-readable result string the assistant
    will speak/display.
    """
    if tool_name == "open_application":
        key = (tool_input.get("name", "") or "").strip().lower()
        alias = APP_ALIASES.get(key)
        if not alias:
            return f"I don't know how to open '{key}'."
        os.system(f"start {alias}")
        return f"Opening {key}."

    if tool_name == "open_website":
        key = (tool_input.get("url_or_alias", "") or "").strip().lower()
        url = WEBSITE_ALLOWLIST.get(key)
        if not url:
            return "That site isn't on the allowlist."
        webbrowser.open(url)
        return f"Opening {url}."

    if tool_name == "write_file":
        path = tool_input.get("path", "")
        content = tool_input.get("content", "") or ""
        try:
            abs_path = _resolve_under_workspace(workspace_dir, path)
        except ValueError as e:
            return str(e)
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return f"Wrote {len(content)} characters to {abs_path}."

    if tool_name == "set_reminder":
        message = (tool_input.get("message", "") or "").strip()
        fire_at_iso = tool_input.get("fire_at_iso", "")
        try:
            fire_at = datetime.fromisoformat(fire_at_iso)
        except (TypeError, ValueError):
            return f"'{fire_at_iso}' is not a valid ISO timestamp."

        entry = {
            "id": str(int(time.time() * 1000)),
            "message": message,
            "fire_at_iso": fire_at.isoformat(),
            "created_at_iso": datetime.now().isoformat(),
        }
        # Resolve reminders_path: if relative, anchor to the project dir.
        if not os.path.isabs(reminders_path):
            reminders_path_abs = os.path.join(os.path.dirname(__file__), reminders_path)
        else:
            reminders_path_abs = reminders_path

        existing: List[Dict[str, Any]] = []
        if os.path.exists(reminders_path_abs):
            try:
                with open(reminders_path_abs, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
                if not isinstance(existing, list):
                    existing = []
            except (OSError, ValueError):
                existing = []
        existing.append(entry)
        with open(reminders_path_abs, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, indent=2)
        return f"Reminder saved for {fire_at.strftime('%Y-%m-%d %H:%M')}."

    if tool_name == "run_shell_command":
        command = (tool_input.get("command", "") or "").strip()
        if not _SAFE_SHELL_RX.match(command):
            return "command not in allowlist, please run it manually."
        head = command.split(maxsplit=1)[0].lower()
        if head not in SHELL_ALLOWLIST:
            return "command not in allowlist, please run it manually."
        try:
            import subprocess
            completed = subprocess.run(
                command.split(),
                shell=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            output = output.strip()
            if not output:
                output = "(no output)"
            if len(output) > SHELL_OUTPUT_MAX_CHARS:
                output = output[:SHELL_OUTPUT_MAX_CHARS] + "\n[...truncated]"
            return f"`{command}` ->\n{output}"
        except subprocess.TimeoutExpired:
            return f"`{command}` timed out after 15 seconds."
        except Exception as e:
            return f"`{command}` failed: {e}"

    if tool_name == "close_app":
        try:
            import pyautogui
            time.sleep(0.5)
            pyautogui.hotkey("alt", "f4")
            return "Sent Alt+F4 to the active window."
        except Exception as e:
            return f"Could not send Alt+F4: {e}"

    return f"Unknown tool: {tool_name}"


def invoke_tool(tool_name: str, tool_input: Dict[str, Any], workspace_dir: str) -> ToolOutcome:
    """Public dispatch entry point used by the executor."""
    return _invoke(tool_name, tool_input, workspace_dir)
