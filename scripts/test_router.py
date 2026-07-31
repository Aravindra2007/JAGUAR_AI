"""
Smoke test for the Jaguar AI tool-use path.

Exercises:
  - tools.py wrappers (workspace enforcement + shell allowlist)
  - tool_executor.execute (auto-completion + confirmation envelope)
  - tool_executor.execute_confirmed (Approve / Deny path)
  - confirmations helpers

Does NOT touch the live Anthropic API - to test the Claude loop end
to end, set ANTHROPIC_API_KEY and run streamlit, then drive it through
the chat input.

Run:
    /d/JAGUAR_AI/myenv/Scripts/python.exe scripts/test_router.py
"""

from __future__ import annotations

import os
import sys
import tempfile

# Make sibling imports work when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import state
import tools
import tool_executor
from tool_executor import ToolExecutor
import confirmations


PASS = "  [PASS]"
FAIL = "  [FAIL]"


def assert_eq(label, got, expected):
    ok = got == expected
    print(f"{PASS if ok else FAIL} {label}: got={got!r}, expected={expected!r}")
    return ok


def assert_in(label, needle, haystack):
    ok = needle in (haystack or "")
    print(f"{PASS if ok else FAIL} {label}: needle={needle!r} in={needle in (haystack or '')}")
    return ok


def main():
    failures = 0

    with tempfile.TemporaryDirectory() as workspace:
        print(f"Workspace: {workspace}")
        # Write a known file we'll try to read.
        with open(os.path.join(workspace, "hello.txt"), "w", encoding="utf-8") as fh:
            fh.write("hello from a tool test")

        # ---- 1. Workspace enforcement ----
        outcome = tools.read_file("hello.txt", workspace_dir=workspace)
        failures += not assert_eq("read_file inside workspace", outcome.mutating, False)
        failures += not assert_in("read_file returns content", "hello from a tool test", outcome.text)

        outcome = tools.read_file("C:/Windows/System32/drivers/etc/hosts", workspace_dir=workspace)
        failures += not assert_in("read_file outside workspace refused", "outside the workspace", outcome.text)

        outcome = tools.list_directory(".", workspace_dir=workspace)
        failures += not assert_in("list_directory sees hello.txt", "hello.txt", outcome.text)

        outcome = tools.list_directory("../", workspace_dir=workspace)
        failures += not assert_in("list_directory .. refused", "outside the workspace", outcome.text)

        # ---- 2. Shell allowlist enforcement ----
        outcome = tools.run_shell_command("del foo.txt")
        failures += not assert_in("del refused with literal", "command not in allowlist", outcome.text)

        outcome = tools.run_shell_command("format C:")
        failures += not assert_in("format refused", "command not in allowlist", outcome.text)

        outcome = tools.run_shell_command("rm -rf notes")
        failures += not assert_in("rm refused", "command not in allowlist", outcome.text)

        outcome = tools.run_shell_command("shutdown /s /t 0")
        failures += not assert_in("shutdown refused", "command not in allowlist", outcome.text)

        # Metacharacter injection
        outcome = tools.run_shell_command("dir & del foo.txt")
        failures += not assert_in("dir & del refused (metachar)", "command not in allowlist", outcome.text)

        outcome = tools.run_shell_command("dir; del foo.txt")
        failures += not assert_in("dir; del refused (metachar)", "command not in allowlist", outcome.text)

        outcome = tools.run_shell_command("dir | findstr foo")
        failures += not assert_in("dir | findstr refused (metachar)", "command not in allowlist", outcome.text)

        # ---- 3. Mutating tools request confirmation ----
        outcome = tools.open_application("notepad")
        failures += not assert_eq("open_application mutating=True", outcome.mutating, True)
        failures += not assert_in("open_application prompt", "Open notepad?", outcome.confirmation_prompt)

        outcome = tools.write_file("notes/test.txt", "hi", workspace_dir=workspace)
        failures += not assert_eq("write_file mutating=True", outcome.mutating, True)
        # The prompt shows the resolved absolute path, not the relative
        # input - either is acceptable, just confirm a path is present.
        failures += not assert_in("write_file prompt mentions path", "test.txt", outcome.confirmation_prompt)

        outcome = tools.run_shell_command("dir")
        failures += not assert_eq("run_shell_command mutating=True", outcome.mutating, True)
        failures += not assert_in("run_shell_command prompt", "Run shell command 'dir'?", outcome.confirmation_prompt)

        outcome = tools.close_app()
        failures += not assert_eq("close_app mutating=True", outcome.mutating, True)

        # ---- 4. Tool executor: read-only returns result kind ----
        executor = ToolExecutor(workspace_dir=workspace)
        result = executor.execute("read_file", {"path": "hello.txt"})
        failures += not assert_eq("executor read_file.kind == result", result["kind"], "result")
        failures += not assert_in("executor read_file text", "hello from a tool test", result["text"])

        # ---- 5. Tool executor: mutating returns confirmation kind ----
        result = executor.execute("write_file", {"path": "test_out.txt", "content": "x"})
        failures += not assert_eq("executor write_file.kind == confirmation", result["kind"], "confirmation")
        failures += not assert_in("executor write_file prompt", "Write", result["prompt"])
        token = result["token"]
        # State should now hold the pending envelope.
        failures += not assert_eq("state has pending envelope", state.peek_pending_confirmation(token) is not None, True)

        # ---- 6. Deny path ----
        result_text = executor.execute_confirmed(token, "no")
        failures += not assert_eq("execute_confirmed(no)", result_text, "Cancelled.")
        # Path should NOT exist (we never wrote it).
        failures += not assert_eq("file not written on deny", os.path.exists(os.path.join(workspace, "test_out.txt")), False)
        # Token is gone.
        failures += not assert_eq("token removed after deny", state.peek_pending_confirmation(token), None)

        # ---- 7. Approve path ----
        result = executor.execute("write_file", {"path": "test_out.txt", "content": "approved!"})
        token2 = result["token"]
        result_text = executor.execute_confirmed(token2, "yes")
        failures += not assert_in("approve wrote the file", "Wrote", result_text)
        # File should now exist with the approved content.
        with open(os.path.join(workspace, "test_out.txt"), "r", encoding="utf-8") as fh:
            content = fh.read()
        failures += not assert_eq("file content after approve", content, "approved!")

    # ---- 8. confirmations helpers ----
    envelope = confirmations.build_envelope("open_application", {"name": "notepad"}, "Open notepad?")
    failures += not assert_eq("is_envelope on dict", confirmations.is_envelope(envelope), True)
    failures += not assert_eq("is_envelope on text", confirmations.is_envelope("hello"), False)
    failures += not assert_eq("confirmation_token extracts token", confirmations.confirmation_token(envelope) is not None, True)
    failures += not assert_eq("format_prompt write_file", confirmations.format_prompt("write_file", {"path": "x", "content": "y"*10}), "Write 10 characters to x?")

    print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} failures")


if __name__ == "__main__":
    main()
