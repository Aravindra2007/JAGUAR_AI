"""
Jaguar AI — System Automation.

Thin wrapper around PyAutoGUI + the standard library for keyboard /
mouse / window-level actions. Used by the planner when a goal needs
desktop automation (typing into native apps, switching windows,
clicking coordinates) rather than browser automation.

All actions are best-effort and return structured results so the
planner can keep going when something fails.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _try_import_pyautogui():
    try:
        import pyautogui  # type: ignore
        return pyautogui
    except Exception:
        return None


@dataclass
class SystemResult:
    ok: bool
    action: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "message": self.message,
            "data": self.data,
        }


class SystemAutomation:
    def __init__(self):
        self.pyautogui = _try_import_pyautogui()
        self._fail_safe = bool(self.pyautogui)

    # ----------------------------------------
    # Apps
    # ----------------------------------------

    def open_app(self, name: str) -> SystemResult:
        name = (name or "").strip()
        if not name:
            return SystemResult(False, "open_app", "No app name.")
        # Windows-friendly start; no-op on macOS/Linux.
        try:
            if os.name == "nt":
                subprocess.Popen(f"start {name}", shell=True)
                return SystemResult(True, "open_app", f"Started {name}")
            else:
                subprocess.Popen([name])
                return SystemResult(True, "open_app", f"Started {name}")
        except Exception as e:
            return SystemResult(False, "open_app", f"Could not open {name}: {e}")

    def close_window(self) -> SystemResult:
        if not self.pyautogui:
            return SystemResult(False, "close_window", "PyAutoGUI not installed.")
        try:
            self.pyautogui.hotkey("alt", "F4")
            return SystemResult(True, "close_window", "Sent Alt+F4.")
        except Exception as e:
            return SystemResult(False, "close_window", str(e))

    # ----------------------------------------
    # Keyboard / mouse
    # ----------------------------------------

    def type_text(self, text: str, interval: float = 0.02) -> SystemResult:
        if not self.pyautogui:
            return SystemResult(False, "type", "PyAutoGUI not installed.")
        try:
            self.pyautogui.typewrite(text, interval=interval) if text.isascii() else self.pyautogui.write(text, interval=interval)
            return SystemResult(True, "type", f"Typed {len(text)} chars")
        except Exception as e:
            return SystemResult(False, "type", str(e))

    def hotkey(self, *keys: str) -> SystemResult:
        if not self.pyautogui:
            return SystemResult(False, "hotkey", "PyAutoGUI not installed.")
        try:
            self.pyautogui.hotkey(*keys)
            return SystemResult(True, "hotkey", f"Pressed {'+'.join(keys)}")
        except Exception as e:
            return SystemResult(False, "hotkey", str(e))

    def press(self, key: str) -> SystemResult:
        if not self.pyautogui:
            return SystemResult(False, "press", "PyAutoGUI not installed.")
        try:
            self.pyautogui.press(key)
            return SystemResult(True, "press", f"Pressed {key}")
        except Exception as e:
            return SystemResult(False, "press", str(e))

    def click(self, x: Optional[int] = None, y: Optional[int] = None,
              button: str = "left") -> SystemResult:
        if not self.pyautogui:
            return SystemResult(False, "click", "PyAutoGUI not installed.")
        try:
            if x is None or y is None:
                self.pyautogui.click(button=button)
            else:
                self.pyautogui.click(x=int(x), y=int(y), button=button)
            return SystemResult(True, "click", "Clicked.")
        except Exception as e:
            return SystemResult(False, "click", str(e))

    def wait(self, seconds: float) -> SystemResult:
        time.sleep(max(0.0, float(seconds)))
        return SystemResult(True, "wait", f"Waited {seconds}s")

    # ----------------------------------------
    # Clipboard
    # ----------------------------------------

    def clipboard_set(self, text: str) -> SystemResult:
        try:
            import pyperclip  # type: ignore
            pyperclip.copy(text)
            return SystemResult(True, "clipboard_set", "Copied to clipboard.")
        except Exception as e:
            return SystemResult(False, "clipboard_set", str(e))

    def clipboard_get(self) -> SystemResult:
        try:
            import pyperclip  # type: ignore
            txt = pyperclip.paste()
            return SystemResult(True, "clipboard_get", "OK", {"text": txt})
        except Exception as e:
            return SystemResult(False, "clipboard_get", str(e))
