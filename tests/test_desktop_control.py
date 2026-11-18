import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from router import CommandRouter
from tools import invoke_tool, run_confirmed


class DesktopToolTests(unittest.TestCase):
    def test_desktop_actions_request_confirmation(self):
        cases = (
            ("desktop_click", {"target_text": "Search"}, "Click the visible screen text"),
            ("desktop_type", {"text": "Hello Jaguar"}, "Type this text"),
            ("desktop_press", {"key": "enter"}, "Press the enter key"),
            ("desktop_hotkey", {"keys": ["ctrl", "f"]}, "Press the ctrl+f keyboard shortcut"),
        )

        for tool_name, tool_input, prompt_fragment in cases:
            with self.subTest(tool_name=tool_name):
                outcome = invoke_tool(tool_name, tool_input, "")
                self.assertTrue(outcome.mutating)
                self.assertIn(prompt_fragment, outcome.confirmation_prompt)

    def test_text_click_uses_unique_local_ocr_match(self):
        pyautogui = Mock()
        pyautogui.size.return_value = (800, 600)
        detected = {
            "text": ["", "Search", "button"],
            "block_num": [1, 1, 1],
            "par_num": [1, 1, 1],
            "line_num": [1, 1, 1],
            "left": [0, 100, 160],
            "top": [0, 200, 200],
            "width": [0, 50, 60],
            "height": [0, 20, 20],
        }
        pytesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=Mock(return_value=detected),
        )

        with patch.dict(sys.modules, {
            "pyautogui": pyautogui,
            "pytesseract": pytesseract,
        }):
            result = run_confirmed(
                "desktop_click",
                {"target_text": "Search button"},
                "",
            )

        self.assertTrue(result["success"])
        pyautogui.click.assert_called_once_with(x=125, y=210, button="left")

    def test_text_click_refuses_ambiguous_match(self):
        pyautogui = Mock()
        pyautogui.size.return_value = (800, 600)
        detected = {
            "text": ["Search", "Search"],
            "block_num": [1, 1],
            "par_num": [1, 1],
            "line_num": [1, 2],
            "left": [100, 300],
            "top": [200, 200],
            "width": [50, 50],
            "height": [20, 20],
        }
        pytesseract = SimpleNamespace(
            Output=SimpleNamespace(DICT="dict"),
            image_to_data=Mock(return_value=detected),
        )

        with patch.dict(sys.modules, {
            "pyautogui": pyautogui,
            "pytesseract": pytesseract,
        }):
            result = run_confirmed(
                "desktop_click",
                {"target_text": "Search"},
                "",
            )

        self.assertFalse(result["success"])
        self.assertIn("more than one", result["text"])
        pyautogui.click.assert_not_called()

    def test_router_preserves_typed_text_and_resolves_button_label(self):
        router = CommandRouter()
        executor = Mock()
        executor.execute.return_value = {
            "kind": "confirmation",
            "token": "approval-token",
            "tool_name": "desktop_type",
            "tool_input": {"text": "Hello Jaguar"},
            "prompt": "Type this text?",
        }

        with patch(
            "router.state.get_llm_config",
            return_value={"tools_enabled": True, "workspace_dir": ""},
        ), patch("router.ToolExecutor", return_value=executor):
            typed = router.process("type Hello Jaguar")
            clicked = router.process("click the X button")

        self.assertEqual(executor.execute.call_args_list[0].args, (
            "desktop_type",
            {"text": "Hello Jaguar"},
        ))
        self.assertEqual(executor.execute.call_args_list[1].args, (
            "desktop_click",
            {"target_text": "X"},
        ))
        self.assertEqual(typed["type"], "needs_confirmation")
        self.assertEqual(clicked["type"], "needs_confirmation")


if __name__ == "__main__":
    unittest.main()
