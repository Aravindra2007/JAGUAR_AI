import os
import tempfile
import unittest
from unittest.mock import patch

from observer import ObservationEngine
from tool_executor import ToolExecutor
from tools import run_confirmed


class ObservationEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.observer = ObservationEngine(self.temp_dir.name)

    def test_verifies_folder_exists_on_disk(self):
        path = os.path.join(self.temp_dir.name, "Project")
        os.mkdir(path)

        observation = self.observer.verify(
            "create_folder",
            {"path": "Project"},
            {"success": True, "text": "Folder created."},
        )

        self.assertEqual(observation["status"], "verified")
        self.assertTrue(observation["verified"])

    def test_detects_tool_claiming_file_write_without_file(self):
        observation = self.observer.verify(
            "write_file",
            {"path": "missing.py", "content": "print('hello')"},
            {"success": True, "text": "Wrote file."},
        )

        self.assertEqual(observation["status"], "failed")
        self.assertEqual(observation["failure_type"], "recoverable")

    def test_unknown_confirmed_tool_is_not_assumed_successful(self):
        observation = self.observer.verify(
            "unknown_tool",
            {},
            {"success": True, "text": "It worked."},
        )

        self.assertEqual(observation["status"], "unverified")
        self.assertFalse(observation["verified"])

    def test_website_open_does_not_claim_page_load(self):
        observation = self.observer.verify(
            "open_website",
            {"url_or_alias": "google"},
            {"success": True, "text": "Opening Google."},
        )

        self.assertEqual(observation["status"], "unverified")
        self.assertIn("page load", observation["message"])

    def test_confirmed_result_uses_independent_verification(self):
        executor = ToolExecutor(workspace_dir=self.temp_dir.name)
        pending = executor.execute(
            "write_file",
            {"path": "not-created.txt", "content": "claimed"},
        )

        with patch(
            "tool_executor.run_confirmed",
            return_value={"success": True, "text": "Write reported successful."},
        ):
            result = executor.execute_confirmed_result(pending["token"], "yes")

        self.assertFalse(result["success"])
        self.assertEqual(result["observation"]["status"], "failed")

    def test_failure_categories_distinguish_input_and_permission(self):
        self.assertEqual(
            self.observer.classify_failure("Missing required tool input: path."),
            "needs_user_input",
        )
        self.assertEqual(
            self.observer.classify_failure("Permission denied."),
            "unrecoverable",
        )
        self.assertEqual(
            self.observer.classify_failure("Network timeout."),
            "recoverable",
        )

    def test_reminder_is_saved_and_verified_in_firestore(self):
        fire_at = "2026-11-11T04:30:00+00:00"
        with patch(
            "db.save_reminder",
            return_value={
                "id": "reminder-1",
                "fire_at_iso": fire_at,
            },
        ) as save_reminder:
            result = run_confirmed(
                "set_reminder",
                {"message": "Call home", "fire_at_iso": fire_at},
                workspace_dir=self.temp_dir.name,
                user_id="account-1",
            )

        save_reminder.assert_called_once()
        self.assertEqual(save_reminder.call_args.args[0], "account-1")
        observer = ObservationEngine(
            self.temp_dir.name,
            user_id="account-1",
        )
        with patch(
            "db.get_reminder",
            return_value={
                "id": "reminder-1",
                "user_id": "account-1",
                "message": "Call home",
                "fire_at_iso": fire_at,
                "status": "pending",
            },
        ):
            observation = observer.verify(
                "set_reminder",
                {"message": "Call home", "fire_at_iso": fire_at},
                result,
            )

        self.assertTrue(observation["verified"])


if __name__ == "__main__":
    unittest.main()
