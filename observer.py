"""Independent verification and failure classification for tool results."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from tools import APP_ALIASES, WEBSITE_ALLOWLIST, _resolve_under_workspace


class ObservationEngine:
    def __init__(
        self,
        workspace_dir: str = "",
        user_id: Optional[str] = None,
    ):
        self.workspace_dir = os.path.abspath(os.path.expanduser(workspace_dir or "~"))
        self.user_id = str(user_id or "")

    def verify(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        execution_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(execution_result, dict):
            return self._unverified("Tool returned no structured execution result.")
        if not execution_result.get("success", False):
            message = str(execution_result.get("text") or "Tool execution failed.")
            return {
                "status": "failed",
                "verified": False,
                "failure_type": self.classify_failure(message),
                "message": message,
            }

        try:
            if tool_name in {"create_folder", "open_folder"}:
                path = _resolve_under_workspace(self.workspace_dir, tool_input["path"])
                if os.path.isdir(path):
                    if tool_name == "create_folder":
                        return self._verified(f"Folder exists: {path}")
                    return self._unverified(
                        f"Folder exists: {path}; File Explorer launch could not be independently confirmed."
                    )
                return self._failed(f"Folder does not exist: {path}", "recoverable")

            if tool_name == "write_file":
                path = _resolve_under_workspace(self.workspace_dir, tool_input["path"])
                if not os.path.isfile(path):
                    return self._failed(f"File was not created: {path}", "recoverable")
                with open(path, "r", encoding="utf-8", errors="replace") as file:
                    actual_content = file.read()
                if actual_content != tool_input["content"]:
                    return self._failed(f"File contents do not match: {path}", "recoverable")
                return self._verified(f"File and contents verified: {path}")

            if tool_name == "read_file":
                if not isinstance(execution_result.get("text"), str):
                    return self._failed("Read tool did not return file content.", "recoverable")
                return self._verified("File content was returned.")

            if tool_name == "list_directory":
                if str(execution_result.get("text", "")).startswith("Directory listing of "):
                    return self._verified("Directory listing was returned.")
                return self._failed(
                    execution_result.get("text") or "Directory listing was not returned.",
                    "recoverable",
                )

            if tool_name == "open_application":
                pid = (execution_result.get("data") or {}).get("pid")
                if pid is None:
                    return self._unverified("Launch was requested; no process identifier was returned.")
                try:
                    import psutil
                except ImportError:
                    return self._unverified("Process inspection is unavailable.")
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        expected = APP_ALIASES[tool_input["name"].strip().lower()].casefold()
                        actual = process.name().casefold()
                        if expected in actual or actual in expected:
                            return self._verified(f"Application process is running: {actual}")
                except (KeyError, OSError, psutil.Error):
                    return self._failed("The requested application process was not found.", "recoverable")
                return self._failed("The requested application process was not found.", "recoverable")

            if tool_name == "open_website":
                if tool_input.get("url_or_alias", "").strip().lower() in WEBSITE_ALLOWLIST:
                    return self._unverified(
                        "Browser launch was requested; page load cannot be independently verified."
                    )
                return self._failed("Website is not on the allowlist.", "unrecoverable")

            if tool_name == "set_reminder":
                return self._verify_reminder(tool_input, execution_result)

            return self._unverified(
                f"Execution returned success for '{tool_name}', but no independent verifier is available."
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            return self._failed(f"Verification failed: {error}", "unrecoverable")

    def _verify_reminder(
        self,
        tool_input: Dict[str, Any],
        execution_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self.user_id:
            return self._failed(
                "Could not verify reminder without an authenticated user.",
                "needs_user_input",
            )
        try:
            expected = datetime.fromisoformat(tool_input["fire_at_iso"])
            if expected.tzinfo is None:
                expected = expected.astimezone()
            expected_time = expected.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, KeyError) as error:
            return self._failed(f"Invalid reminder timestamp: {error}", "unrecoverable")
        entry_id = (execution_result.get("data") or {}).get("id")
        try:
            import db

            reminder = db.get_reminder(self.user_id, entry_id) if entry_id else None
        except Exception as error:
            return self._failed(
                f"Could not verify saved reminder in Firestore: {error}",
                "recoverable",
            )
        matching = bool(
            reminder
            and reminder.get("message") == tool_input.get("message", "").strip()
            and reminder.get("fire_at_iso") == expected_time
        )
        if matching:
            return self._verified("Reminder entry was found in Firestore.")
        return self._failed("Reminder entry was not found in Firestore.", "recoverable")

    @staticmethod
    def classify_failure(message: str) -> str:
        normalized = message.casefold()
        if any(value in normalized for value in ("permission", "access is denied", "not allowed")):
            return "unrecoverable"
        if any(value in normalized for value in ("cancelled", "denied", "expired")):
            return "needs_user_input"
        if any(value in normalized for value in ("invalid", "must be", "missing required")):
            return "needs_user_input"
        if any(value in normalized for value in ("timed out", "timeout", "network")):
            return "recoverable"
        if any(value in normalized for value in ("not found", "does not exist", "already exists")):
            return "recoverable"
        return "unrecoverable"

    @staticmethod
    def _verified(message: str) -> Dict[str, Any]:
        return {
            "status": "verified",
            "verified": True,
            "failure_type": None,
            "message": message,
        }

    @staticmethod
    def _unverified(message: str) -> Dict[str, Any]:
        return {
            "status": "unverified",
            "verified": False,
            "failure_type": "unrecoverable",
            "message": message,
        }

    @staticmethod
    def _failed(message: str, failure_type: str) -> Dict[str, Any]:
        return {
            "status": "failed",
            "verified": False,
            "failure_type": failure_type,
            "message": str(message),
        }
