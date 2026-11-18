"""
Jaguar AI tool catalog and guarded action implementations.

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

This split keeps both the plan executor and model tool loops simple:
they call executor.execute(name, input) and receive either a result or
a confirmation envelope. No tools here should ever call
subprocess / os.system / webbrowser / pyautogui directly — those
happen only inside execute_confirmed.
"""

from __future__ import annotations

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

ToolOutcome = namedtuple(
    "ToolOutcome",
    "text mutating confirmation_prompt success",
    defaults=(True,),
)


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
    "gmail": "https://mail.google.com",
    "spotify": "https://open.spotify.com",
    "github": "https://github.com",
    "chatgpt": "https://chat.openai.com",
    "stack overflow": "https://stackoverflow.com",
    "wikipedia": "https://wikipedia.org",
    "irctc": "https://www.irctc.co.in",
    "bookmyshow": "https://in.bookmyshow.com",
    "redbus": "https://www.redbus.in",
    "tirupati": "https://tirupatibalaji.ap.gov.in",
}

WORKSPACE_MAX_READ_CHARS = 8000
SHELL_OUTPUT_MAX_CHARS = 4000
MAX_DESKTOP_TEXT_CHARS = 2000

DESKTOP_KEYS = {
    *(chr(code) for code in range(ord("a"), ord("z") + 1)),
    *(str(number) for number in range(10)),
    *(f"f{number}" for number in range(1, 13)),
    "alt", "backspace", "capslock", "ctrl", "delete", "down", "end",
    "enter", "esc", "home", "insert", "left", "pagedown", "pageup",
    "right", "shift", "space", "tab", "up", "win",
}

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
    workspace_abs = os.path.realpath(os.path.abspath(workspace_dir))

    if os.path.isabs(path):
        candidate = os.path.realpath(os.path.abspath(path))
    else:
        candidate = os.path.realpath(os.path.abspath(os.path.join(workspace_abs, path)))

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
            success=False,
        )
    return ToolOutcome(
        text=f"Will launch {APP_ALIASES[key]}.",
        mutating=True,
        confirmation_prompt=f"Open {key}?",
    )


def open_website(url_or_alias: str, workspace_dir: str = "") -> ToolOutcome:
    """Open an allowlisted website after the user confirms."""
    key = (url_or_alias or "").strip().lower()
    if key in WEBSITE_ALLOWLIST:
        return ToolOutcome(
            text=f"Will open {WEBSITE_ALLOWLIST[key]}.",
            mutating=True,
            confirmation_prompt=f"Open {key}?",
        )
    return ToolOutcome(
        text=(
            "That site isn't on the allowlist. Allowed: "
            + ", ".join(sorted(WEBSITE_ALLOWLIST)) + "."
        ),
        mutating=False,
        confirmation_prompt=None,
        success=False,
    )


def list_directory(path: str, workspace_dir: str) -> ToolOutcome:
    """Read-only: list a directory under the workspace."""
    if not workspace_dir:
        return ToolOutcome(
            text="No workspace folder is configured.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path or ".")
    except ValueError as e:
        return ToolOutcome(text=str(e), mutating=False, confirmation_prompt=None, success=False)

    if not os.path.isdir(abs_path):
        return ToolOutcome(
            text=f"{abs_path} is not a directory.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )

    try:
        return ToolOutcome(
            text=_format_dir_listing(workspace_dir, abs_path),
            mutating=False,
            confirmation_prompt=None,
        )
    except OSError as e:
        return ToolOutcome(text=f"Could not list directory: {e}", mutating=False, confirmation_prompt=None, success=False)


def read_file(path: str, workspace_dir: str) -> ToolOutcome:
    """Read supported text, PDF, Word, and image files under the workspace."""
    if not workspace_dir:
        return ToolOutcome(
            text="No workspace folder is configured.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path)
    except ValueError as e:
        return ToolOutcome(text=str(e), mutating=False, confirmation_prompt=None, success=False)

    if not os.path.isfile(abs_path):
        return ToolOutcome(
            text=f"{abs_path} is not a file.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )

    extension = os.path.splitext(abs_path)[1].lower()
    import file_reader
    reader_extensions = (
        file_reader.PDF_EXTENSIONS
        | file_reader.DOCX_EXTENSIONS
        | file_reader.IMAGE_EXTENSIONS
    )
    if extension in reader_extensions:
        content = file_reader.extract_text(abs_path)
        if content.startswith((
            "(Could not",
            "(PDF reading requires",
            "(Word reading requires",
            "(Image received.",
            "(No extractable text found in this PDF.",
        )):
            return ToolOutcome(
                text=content,
                mutating=False,
                confirmation_prompt=None,
                success=False,
            )
    else:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read(WORKSPACE_MAX_READ_CHARS)
        except OSError as e:
            return ToolOutcome(text=f"Could not read file: {e}", mutating=False, confirmation_prompt=None, success=False)

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
            success=False,
        )
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path)
    except ValueError as e:
        return ToolOutcome(text=str(e), mutating=False, confirmation_prompt=None, success=False)

    if os.path.lexists(abs_path):
        return ToolOutcome(
            text=f"{abs_path} already exists. Choose a different path; existing files are not overwritten.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )
    parent = os.path.dirname(abs_path)
    if not os.path.isdir(parent):
        return ToolOutcome(
            text=f"Parent directory does not exist: {parent}",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )

    return ToolOutcome(
        text=f"Will write {len(content or '')} characters to {abs_path}.",
        mutating=True,
        confirmation_prompt=(
            f"Write {len(content or '')} characters to {abs_path}? "
            f"Approving also allows creating additional files in {os.path.dirname(abs_path)} "
            "without asking again until Jaguar restarts. Existing files are never overwritten."
        ),
    )


def create_folder(path: str, workspace_dir: str) -> ToolOutcome:
    if not workspace_dir:
        return ToolOutcome("No workspace folder is configured.", False, None, False)
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path)
    except ValueError as e:
        return ToolOutcome(str(e), False, None, False)
    if os.path.isdir(abs_path):
        return ToolOutcome(
            f"Folder already exists: {abs_path}.",
            False,
            None,
        )
    if os.path.lexists(abs_path):
        return ToolOutcome(f"{abs_path} already exists.", False, None, False)
    parent = os.path.dirname(abs_path)
    if not os.path.isdir(parent):
        return ToolOutcome(f"Parent directory does not exist: {parent}", False, None, False)
    return ToolOutcome(
        f"Will create folder {abs_path}.",
        True,
        f"Create folder {abs_path}?",
    )


def open_folder(path: str, workspace_dir: str) -> ToolOutcome:
    if not workspace_dir:
        return ToolOutcome("No workspace folder is configured.", False, None, False)
    try:
        abs_path = _resolve_under_workspace(workspace_dir, path)
    except ValueError as e:
        return ToolOutcome(str(e), False, None, False)
    if not os.path.isdir(abs_path):
        return ToolOutcome(f"{abs_path} is not a directory.", False, None, False)
    return ToolOutcome(
        f"Will open folder {abs_path}.",
        True,
        f"Open folder {abs_path}?",
    )


def set_reminder(message: str, fire_at_iso: str, workspace_dir: str = "") -> ToolOutcome:
    """Mutating: schedule a reminder after user approval."""
    message = (message or "").strip()
    if not message:
        return ToolOutcome(
            text="Reminder message cannot be empty.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )
    try:
        fire_at = datetime.fromisoformat(fire_at_iso)
    except (TypeError, ValueError):
        return ToolOutcome(
            text=f"'{fire_at_iso}' is not a valid ISO timestamp.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
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
            success=False,
        )

    if not _SAFE_SHELL_RX.match(command):
        return ToolOutcome(
            text="command not in allowlist, please run it manually.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
        )

    head = command.split(maxsplit=1)[0].lower()
    if head not in SHELL_ALLOWLIST:
        return ToolOutcome(
            text="command not in allowlist, please run it manually.",
            mutating=False,
            confirmation_prompt=None,
            success=False,
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


def desktop_click(
    target_text: str = "",
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    workspace_dir: str = "",
) -> ToolOutcome:
    target_text = (target_text or "").strip()
    if bool(target_text) == (x is not None or y is not None):
        return ToolOutcome(
            "Specify either visible target text or both screen coordinates.",
            False,
            None,
            False,
        )
    if (x is None) != (y is None):
        return ToolOutcome("Both x and y coordinates are required.", False, None, False)
    if button not in {"left", "right", "middle"}:
        return ToolOutcome("Mouse button must be left, right, or middle.", False, None, False)

    if target_text:
        prompt = f"Click the visible screen text '{target_text}'?"
        action = f"Click screen text '{target_text}'"
    else:
        prompt = f"Click at screen coordinates ({x}, {y})?"
        action = f"Click at ({x}, {y})"
    if button != "left":
        prompt = f"{prompt[:-1]} with the {button} mouse button?"
        action = f"{action} with the {button} mouse button"
    return ToolOutcome(
        text=f"Will {action}.",
        mutating=True,
        confirmation_prompt=prompt,
    )


def desktop_type(text: str, workspace_dir: str = "") -> ToolOutcome:
    text = text or ""
    if not text.strip():
        return ToolOutcome("Text to type cannot be empty.", False, None, False)
    if len(text) > MAX_DESKTOP_TEXT_CHARS:
        return ToolOutcome(
            f"Text to type cannot exceed {MAX_DESKTOP_TEXT_CHARS} characters.",
            False,
            None,
            False,
        )
    preview = text if len(text) <= 80 else text[:77] + "..."
    return ToolOutcome(
        f"Will type {len(text)} characters.",
        True,
        f"Type this text into the focused window: {preview!r}?",
    )


def desktop_press(key: str, workspace_dir: str = "") -> ToolOutcome:
    key = _normalize_desktop_key(key)
    if key not in DESKTOP_KEYS:
        return ToolOutcome(f"Unsupported keyboard key: {key!r}.", False, None, False)
    return ToolOutcome(
        f"Will press {key}.",
        True,
        f"Press the {key} key?",
    )


def desktop_hotkey(keys: List[str], workspace_dir: str = "") -> ToolOutcome:
    if not isinstance(keys, list) or not 2 <= len(keys) <= 4:
        return ToolOutcome("A keyboard shortcut must contain 2 to 4 keys.", False, None, False)
    normalized = [_normalize_desktop_key(key) for key in keys]
    invalid = [key for key in normalized if key not in DESKTOP_KEYS]
    if invalid:
        return ToolOutcome(
            f"Unsupported keyboard key: {invalid[0]!r}.",
            False,
            None,
            False,
        )
    shortcut = "+".join(normalized)
    return ToolOutcome(
        f"Will press {shortcut}.",
        True,
        f"Press the {shortcut} keyboard shortcut?",
    )


def _normalize_desktop_key(key: str) -> str:
    aliases = {
        "control": "ctrl",
        "escape": "esc",
        "return": "enter",
        "windows": "win",
    }
    normalized = str(key or "").strip().casefold()
    return aliases.get(normalized, normalized)


def _find_screen_text(target_text: str) -> tuple[int, int]:
    """Find one unambiguous OCR text match and return its screen center."""
    try:
        import pyautogui
        import pytesseract
    except ImportError as error:
        raise RuntimeError(
            "Text-based clicking requires PyAutoGUI, pytesseract, and the "
            "Tesseract OCR engine. Use screen coordinates or install them."
        ) from error

    target_words = re.findall(r"\w+", target_text.casefold())
    if target_words and target_words[0] == "the":
        target_words = target_words[1:]
    if target_words and target_words[-1] in {"button", "icon"}:
        target_words = target_words[:-1]
    if not target_words:
        raise ValueError("The screen text to click must include a visible label.")

    image = pyautogui.screenshot()
    detected = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT,
    )
    lines = {}
    for index, value in enumerate(detected.get("text", [])):
        word = re.sub(r"\W+", "", str(value).casefold())
        if not word:
            continue
        line_key = (
            detected["block_num"][index],
            detected["par_num"][index],
            detected["line_num"][index],
        )
        lines.setdefault(line_key, []).append((
            word,
            int(detected["left"][index]),
            int(detected["top"][index]),
            int(detected["width"][index]),
            int(detected["height"][index]),
        ))

    matches = []
    for words in lines.values():
        for start in range(len(words) - len(target_words) + 1):
            selection = words[start:start + len(target_words)]
            if [word[0] for word in selection] != target_words:
                continue
            left = min(word[1] for word in selection)
            top = min(word[2] for word in selection)
            right = max(word[1] + word[3] for word in selection)
            bottom = max(word[2] + word[4] for word in selection)
            matches.append(((left + right) // 2, (top + bottom) // 2))

    if not matches:
        raise ValueError(f"Could not find '{target_text}' on the screen.")
    if len(matches) > 1:
        raise ValueError(
            f"Found more than one '{target_text}' on the screen; use coordinates instead."
        )
    return matches[0]


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
            "the allowlist: google, youtube, gmail, spotify, github, chatgpt, "
            "stack overflow, wikipedia, irctc, bookmyshow, redbus, tirupati. "
            "Requires user confirmation before opening."
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
            "Read a text, PDF, DOCX, or common image file under the workspace. "
            "PDFs and DOCX files have their text extracted; images use OCR and "
            "require pytesseract, Pillow, and the Tesseract engine. Scanned PDFs "
            "without embedded text are not OCR-processed. Output is truncated "
            "to 8000 characters. Refuses paths outside the workspace."
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
        "name": "create_folder",
        "description": (
            "Ensure one directory exists inside the configured workspace. "
            "An existing directory is reported as already satisfied; an existing "
            "non-directory path is refused. Its parent must already exist. "
            "Creating the directory requires user confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "New folder path relative to the workspace.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "open_folder",
        "description": (
            "Open an existing directory inside the configured workspace "
            "in Windows File Explorer. Requires user confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to the workspace.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file under the workspace. Refuses paths "
            "outside the workspace and refuses to overwrite an existing file. "
            "Requires user confirmation before writing."
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
    {
        "name": "desktop_click",
        "description": (
            "Click the user's desktop after confirmation. To click a visible "
            "label or button, provide target_text (for example 'Search' or "
            "'X button'); Jaguar finds a unique OCR match locally. Or provide "
            "both x and y screen coordinates. You may set button to left, "
            "right, or middle. If text is missing or ambiguous, the action "
            "fails safely."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_text": {
                    "type": "string",
                    "description": "Visible text to locate and click.",
                },
                "x": {"type": "integer", "description": "Horizontal screen coordinate."},
                "y": {"type": "integer", "description": "Vertical screen coordinate."},
                "button": {
                    "type": "string",
                    "description": "Mouse button: left, right, or middle.",
                },
            },
        },
    },
    {
        "name": "desktop_type",
        "description": (
            "Type up to 2000 characters into the currently focused desktop "
            "field or application. Requires user confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Exact text to type, preserving capitalization.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "desktop_press",
        "description": (
            "Press one keyboard key in the focused desktop application. "
            "Supported keys include letters, digits, F1-F12, Enter, Escape, "
            "Tab, arrows, Backspace, Delete, and modifier keys. Requires "
            "user confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "One supported key name."},
            },
            "required": ["key"],
        },
    },
    {
        "name": "desktop_hotkey",
        "description": (
            "Press a keyboard shortcut containing 2 to 4 supported keys, "
            "such as ['ctrl', 'f']. Requires user confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Two to four keys in the shortcut.",
                },
            },
            "required": ["keys"],
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
        "create_folder":    lambda i: create_folder(i.get("path", ""), workspace_dir),
        "open_folder":      lambda i: open_folder(i.get("path", ""), workspace_dir),
        "write_file":        lambda i: write_file(i.get("path", ""), i.get("content", ""), workspace_dir),
        "set_reminder":      lambda i: set_reminder(i.get("message", ""), i.get("fire_at_iso", ""), workspace_dir),
        "run_shell_command": lambda i: run_shell_command(i.get("command", ""), workspace_dir),
        "close_app":         lambda i: close_app(workspace_dir),
        "desktop_click":     lambda i: desktop_click(
            i.get("target_text", ""),
            i.get("x"),
            i.get("y"),
            i.get("button", "left"),
            workspace_dir,
        ),
        "desktop_type":      lambda i: desktop_type(i.get("text", ""), workspace_dir),
        "desktop_press":     lambda i: desktop_press(i.get("key", ""), workspace_dir),
        "desktop_hotkey":    lambda i: desktop_hotkey(i.get("keys", []), workspace_dir),
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

def run_confirmed(
    tool_name: str,
    tool_input: Dict[str, Any],
    workspace_dir: str,
    user_id: str = "",
) -> Dict[str, Any]:
    """Perform the actual side effect of a tool the user has approved.

    `tool_input` MUST be the same dict that was passed when generating
    the confirmation envelope. User-owned reminders are stored in Firestore.
    Returns the human-readable result the assistant will speak/display.
    """
    if tool_name == "open_application":
        key = (tool_input.get("name", "") or "").strip().lower()
        alias = APP_ALIASES.get(key)
        if not alias:
            return {"success": False, "text": f"I don't know how to open '{key}'."}
        try:
            import subprocess
            process = subprocess.Popen([alias])
        except OSError as error:
            return {"success": False, "text": f"Could not launch {key}: {error}"}
        return {
            "success": True,
            "text": f"Opening {key}.",
            "data": {"pid": process.pid, "executable": alias},
        }

    if tool_name == "open_website":
        key = (tool_input.get("url_or_alias", "") or "").strip().lower()
        url = WEBSITE_ALLOWLIST.get(key)
        if not url:
            return {"success": False, "text": "That site isn't on the allowlist."}
        if not webbrowser.open(url):
            return {"success": False, "text": f"Could not open {url}."}
        return {"success": True, "text": f"Opening {url}.", "data": {"url": url}}

    if tool_name == "create_folder":
        try:
            abs_path = _resolve_under_workspace(workspace_dir, tool_input.get("path", ""))
            os.mkdir(abs_path)
        except (OSError, ValueError) as e:
            return {"success": False, "text": f"Could not create folder: {e}"}
        return {"success": True, "text": f"Created folder {abs_path}.", "data": {"path": abs_path}}

    if tool_name == "open_folder":
        try:
            abs_path = _resolve_under_workspace(workspace_dir, tool_input.get("path", ""))
            if not os.path.isdir(abs_path):
                return {"success": False, "text": f"{abs_path} is not a directory."}
            os.startfile(abs_path)
        except (OSError, ValueError, AttributeError) as e:
            return {"success": False, "text": f"Could not open folder: {e}"}
        return {"success": True, "text": f"Opened folder {abs_path}.", "data": {"path": abs_path}}

    if tool_name == "write_file":
        path = tool_input.get("path", "")
        content = tool_input.get("content", "") or ""
        try:
            abs_path = _resolve_under_workspace(workspace_dir, path)
        except ValueError as e:
            return {"success": False, "text": str(e)}
        try:
            with open(abs_path, "x", encoding="utf-8") as fh:
                fh.write(content)
        except FileExistsError:
            return {
                "success": False,
                "text": f"{abs_path} already exists. Existing files are not overwritten.",
            }
        except OSError as e:
            return {"success": False, "text": f"Could not write file: {e}"}
        return {
            "success": True,
            "text": f"Wrote {len(content)} characters to {abs_path}.",
            "data": {"path": abs_path},
        }

    if tool_name == "set_reminder":
        message = (tool_input.get("message", "") or "").strip()
        fire_at_iso = tool_input.get("fire_at_iso", "")
        try:
            fire_at = datetime.fromisoformat(fire_at_iso)
        except (TypeError, ValueError):
            return {
                "success": False,
                "text": f"'{fire_at_iso}' is not a valid ISO timestamp.",
            }
        if not user_id:
            return {
                "success": False,
                "text": "Sign in before saving a reminder.",
            }
        import db

        entry = db.save_reminder(user_id, message, fire_at)
        return {
            "success": True,
            "text": f"Reminder saved for {fire_at.strftime('%Y-%m-%d %H:%M')}.",
            "data": {"id": entry["id"], "fire_at_iso": entry["fire_at_iso"]},
        }

    if tool_name == "run_shell_command":
        command = (tool_input.get("command", "") or "").strip()
        if not _SAFE_SHELL_RX.match(command):
            return {
                "success": False,
                "text": "command not in allowlist, please run it manually.",
            }
        head = command.split(maxsplit=1)[0].lower()
        if head not in SHELL_ALLOWLIST:
            return {
                "success": False,
                "text": "command not in allowlist, please run it manually.",
            }
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
            if completed.returncode != 0:
                return {
                    "success": False,
                    "text": f"`{command}` failed with exit code {completed.returncode}:\n{output}",
                    "data": {"returncode": completed.returncode},
                }
            return {
                "success": True,
                "text": f"`{command}` ->\n{output}",
                "data": {"returncode": completed.returncode, "output": output},
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "text": f"`{command}` timed out after 15 seconds."}
        except Exception as e:
            return {"success": False, "text": f"`{command}` failed: {e}"}

    if tool_name == "close_app":
        try:
            import pyautogui
            time.sleep(0.5)
            pyautogui.hotkey("alt", "f4")
            return {"success": True, "text": "Sent Alt+F4 to the active window."}
        except Exception as e:
            return {"success": False, "text": f"Could not send Alt+F4: {e}"}

    if tool_name == "desktop_click":
        try:
            import pyautogui
            target_text = (tool_input.get("target_text") or "").strip()
            x = tool_input.get("x")
            y = tool_input.get("y")
            button = tool_input.get("button", "left")
            if button not in {"left", "right", "middle"}:
                return {"success": False, "text": "Mouse button must be left, right, or middle."}
            if target_text:
                if x is not None or y is not None:
                    return {
                        "success": False,
                        "text": "Specify either visible target text or screen coordinates, not both.",
                    }
                x, y = _find_screen_text(target_text)
            elif x is None or y is None:
                return {
                    "success": False,
                    "text": "Specify visible target text or both screen coordinates.",
                }
            width, height = pyautogui.size()
            if not (0 <= int(x) < width and 0 <= int(y) < height):
                return {
                    "success": False,
                    "text": f"Screen coordinates must be within {width}x{height}.",
                }
            pyautogui.click(x=int(x), y=int(y), button=button)
            return {
                "success": True,
                "text": f"Clicked at ({int(x)}, {int(y)}).",
                "data": {"x": int(x), "y": int(y), "button": button},
            }
        except Exception as error:
            return {"success": False, "text": f"Could not click the desktop: {error}"}

    if tool_name == "desktop_type":
        text = tool_input.get("text") or ""
        if not text.strip():
            return {"success": False, "text": "Text to type cannot be empty."}
        if len(text) > MAX_DESKTOP_TEXT_CHARS:
            return {
                "success": False,
                "text": f"Text to type cannot exceed {MAX_DESKTOP_TEXT_CHARS} characters.",
            }
        try:
            import pyautogui
            pyautogui.write(text, interval=0.02)
            return {"success": True, "text": f"Typed {len(text)} characters."}
        except Exception as error:
            return {"success": False, "text": f"Could not type text: {error}"}

    if tool_name == "desktop_press":
        key = _normalize_desktop_key(tool_input.get("key", ""))
        if key not in DESKTOP_KEYS:
            return {"success": False, "text": f"Unsupported keyboard key: {key!r}."}
        try:
            import pyautogui
            pyautogui.press(key)
            return {"success": True, "text": f"Pressed {key}."}
        except Exception as error:
            return {"success": False, "text": f"Could not press {key}: {error}"}

    if tool_name == "desktop_hotkey":
        keys = tool_input.get("keys", [])
        if not isinstance(keys, list) or not 2 <= len(keys) <= 4:
            return {"success": False, "text": "A keyboard shortcut must contain 2 to 4 keys."}
        keys = [_normalize_desktop_key(key) for key in keys]
        invalid = [key for key in keys if key not in DESKTOP_KEYS]
        if invalid:
            return {"success": False, "text": f"Unsupported keyboard key: {invalid[0]!r}."}
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            return {"success": True, "text": f"Pressed {'+'.join(keys)}."}
        except Exception as error:
            return {"success": False, "text": f"Could not press shortcut: {error}"}

    return {"success": False, "text": f"Unknown tool: {tool_name}"}


def invoke_tool(tool_name: str, tool_input: Dict[str, Any], workspace_dir: str) -> ToolOutcome:
    """Public dispatch entry point used by the executor."""
    return _invoke(tool_name, tool_input, workspace_dir)
