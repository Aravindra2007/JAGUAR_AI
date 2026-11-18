import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import speech_recognition as sr

from listener import CONFIRMATION_LISTEN_ATTEMPTS, VoiceListener
import state
from router import CommandRouter
from tool_executor import ToolExecutor


class ToolExecutorSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.executor = ToolExecutor(workspace_dir=self.temp_dir.name)

    def test_rejects_missing_extra_and_wrongly_typed_arguments(self):
        cases = [
            ("write_file", {"path": "note.txt"}),
            ("read_file", {"path": "note.txt", "unexpected": True}),
            ("list_directory", {"path": 42}),
        ]

        for tool_name, tool_input in cases:
            with self.subTest(tool_name=tool_name, tool_input=tool_input):
                result = self.executor.execute(tool_name, tool_input)
                self.assertEqual(result["kind"], "result")
                self.assertIn("input", result["text"].lower())

    def test_rejects_tools_outside_configured_allowlist(self):
        executor = ToolExecutor(
            workspace_dir=self.temp_dir.name,
            allowlist={"read_file"},
        )

        result = executor.execute("list_directory", {"path": "."})

        self.assertIn("not allowed", result["text"])

    def test_existing_file_is_not_overwritten(self):
        target = os.path.join(self.temp_dir.name, "note.txt")
        with open(target, "w", encoding="utf-8") as file:
            file.write("keep this")

        result = self.executor.execute(
            "write_file",
            {"path": "note.txt", "content": "replace this"},
        )

        self.assertEqual(result["kind"], "result")
        self.assertIn("not overwritten", result["text"])
        with open(target, encoding="utf-8") as file:
            self.assertEqual(file.read(), "keep this")

    def test_read_file_extracts_pdf_and_image_text(self):
        for filename, extracted in (
            ("report.pdf", "PDF contents"),
            ("diagram.png", "Image OCR contents"),
        ):
            with self.subTest(filename=filename):
                path = os.path.join(self.temp_dir.name, filename)
                with open(path, "wb") as file:
                    file.write(b"placeholder")

                with patch("file_reader.extract_text", return_value=extracted) as extract:
                    result = self.executor.execute("read_file", {"path": filename})

                self.assertEqual(result["kind"], "result")
                self.assertTrue(result["success"])
                self.assertEqual(result["text"], extracted)
                extract.assert_called_once_with(path)

    def test_read_image_reports_missing_ocr_dependencies(self):
        path = os.path.join(self.temp_dir.name, "diagram.png")
        with open(path, "wb") as file:
            file.write(b"placeholder")

        with patch(
            "file_reader.extract_text",
            return_value="(Image received. Text extraction needs OCR.)",
        ):
            result = self.executor.execute("read_file", {"path": "diagram.png"})

        self.assertEqual(result["kind"], "result")
        self.assertFalse(result["success"])
        self.assertIn("OCR", result["text"])

    def test_approval_is_single_use_and_rechecked_before_writing(self):
        result = self.executor.execute(
            "write_file",
            {"path": "note.txt", "content": "approved"},
        )
        token = result["token"]
        target = os.path.join(self.temp_dir.name, "note.txt")
        with open(target, "w", encoding="utf-8") as file:
            file.write("created while awaiting approval")

        approval_result = self.executor.execute_confirmed(token, "yes")
        repeated_result = self.executor.execute_confirmed(token, "yes")

        self.assertIn("not overwritten", approval_result)
        self.assertIn("expired or was already handled", repeated_result)
        with open(target, encoding="utf-8") as file:
            self.assertEqual(file.read(), "created while awaiting approval")

    def test_expired_confirmation_cannot_be_approved(self):
        state.push_pending_confirmation("expired-token", {
            "tool_name": "write_file",
            "tool_input": {"path": "note.txt", "content": "no"},
            "expires_at": 0,
        })

        result = self.executor.execute_confirmed("expired-token", "yes")

        self.assertIn("Confirmation expired", result)


class ExplicitRoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = object.__new__(CommandRouter)
        self.router.routes = {
            "open google": Mock(name="open_google"),
            "open calculator": Mock(name="open_calculator"),
            "time": Mock(name="time"),
            "search": Mock(name="search"),
        }

    def test_matches_explicit_commands_case_insensitively(self):
        self.assertIs(
            self.router._match_route("  OPEN CALCULATOR "),
            self.router.routes["open calculator"],
        )

    def test_does_not_match_an_incidental_open_keyword(self):
        self.assertIsNone(self.router._match_route("start a new project"))
        self.assertIsNone(self.router._match_route("please open calculator"))
        self.assertIsNone(self.router._match_route("open calculator and search"))

    def test_argument_commands_require_the_route_at_the_start(self):
        self.assertIs(
            self.router._match_route("search machine learning internships"),
            self.router.routes["search"],
        )
        self.assertIsNone(
            self.router._match_route("please search machine learning internships")
        )

    def test_multi_action_phrasing_bypasses_legacy_single_command_routes(self):
        self.assertTrue(
            self.router._is_compound_request(
                "Create a folder, add a Python file and open it"
            )
        )
        self.assertTrue(
            self.router._is_compound_request(
                "Open Chrome and then search for internships"
            )
        )
        self.assertFalse(self.router._is_compound_request("search machine learning"))


class VoiceConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.listener = VoiceListener()
        self.listener.running = True
        self.listener.router = Mock()

    def test_silence_retries_without_becoming_a_denial(self):
        self.listener.recognizer.listen = Mock(
            side_effect=sr.WaitTimeoutError("No confirmation heard.")
        )
        response = {
            "type": "needs_confirmation",
            "envelope": {"token": "pending-token", "prompt": "Open YouTube?"},
        }

        with patch("listener.speak"):
            decision = self.listener._listen_for_confirmation(
                object(),
                "Open YouTube?",
            )
        with patch.object(self.listener, "_defer_unconfirmed_action") as defer:
            result = self.listener._resolve_or_defer_confirmation(
                "Open YouTube",
                response,
                decision,
            )

        self.assertIsNone(decision)
        self.assertIsNone(result)
        self.assertEqual(
            self.listener.recognizer.listen.call_count,
            CONFIRMATION_LISTEN_ATTEMPTS,
        )
        defer.assert_called_once_with("Open YouTube", response)
        self.listener.router.process_with_confirmation.assert_not_called()

    def test_unheard_approval_is_available_in_the_app(self):
        response = {
            "type": "needs_confirmation",
            "envelope": {"token": "pending-token", "prompt": "Open YouTube?"},
        }

        with (
            patch("listener.state.get_current_user_id", return_value="user-1"),
            patch("listener.state.add_web_pending_confirmation") as add_pending,
            patch("listener.state.add_history"),
            patch("listener.state.set_text"),
            patch("listener.state.set_status"),
            patch("listener.state.is_muted", return_value=True),
        ):
            result = self.listener._resolve_or_defer_confirmation(
                "Open YouTube",
                response,
                None,
            )

        self.assertIsNone(result)
        add_pending.assert_called_once_with("user-1", "Open YouTube", response)
        self.listener.router.process_with_confirmation.assert_not_called()

    def test_do_it_is_recognized_as_approval(self):
        self.listener.recognizer.listen = Mock(return_value="audio")
        self.listener.recognizer.recognize_google = Mock(return_value="Do it!")

        with patch("listener.speak"):
            decision = self.listener._listen_for_confirmation(
                object(),
                "Open YouTube?",
            )

        self.assertEqual(decision, "yes")

    def test_explicit_no_still_denies_confirmation(self):
        response = {
            "type": "needs_confirmation",
            "envelope": {"token": "pending-token", "prompt": "Open YouTube?"},
        }
        self.listener.router.process_with_confirmation.return_value = "Cancelled."

        result = self.listener._resolve_or_defer_confirmation(
            "Open YouTube",
            response,
            "no",
        )

        self.assertEqual(result, "Cancelled.")
        self.listener.router.process_with_confirmation.assert_called_once_with(
            "pending-token",
            "no",
        )


if __name__ == "__main__":
    unittest.main()
