import sys
import types
import unittest
from unittest.mock import Mock

from llm_client import ask_gemini


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.models = Mock()
        self.client = Mock()
        self.client.models = self.models

        self.google_module = types.ModuleType("google")
        self.genai_module = types.ModuleType("google.genai")
        self.genai_module.Client = Mock(return_value=self.client)
        self.google_module.genai = self.genai_module

        self.original_google = sys.modules.get("google")
        self.original_genai = sys.modules.get("google.genai")
        sys.modules["google"] = self.google_module
        sys.modules["google.genai"] = self.genai_module

    def tearDown(self):
        if self.original_google is None:
            sys.modules.pop("google", None)
        else:
            sys.modules["google"] = self.original_google

        if self.original_genai is None:
            sys.modules.pop("google.genai", None)
        else:
            sys.modules["google.genai"] = self.original_genai

    def test_gemini_normal_request_uses_google_genai(self):
        self.models.generate_content.return_value = types.SimpleNamespace(text="hello")

        result = ask_gemini(
            [{"role": "user", "content": "Say hello"}],
            api_key="test-key",
            model="gemini-test",
            temperature=0.25,
            stream=False,
        )

        self.assertEqual(result, "hello")
        self.genai_module.Client.assert_called_once_with(api_key="test-key")
        self.models.generate_content.assert_called_once_with(
            model="gemini-test",
            contents="[USER]: Say hello\n",
            config={"temperature": 0.25},
        )

    def test_gemini_stream_request_uses_google_genai(self):
        self.models.generate_content_stream.return_value = iter([
            types.SimpleNamespace(text="hel"),
            types.SimpleNamespace(text="lo"),
        ])

        result = ask_gemini(
            [{"role": "user", "content": "Say hello"}],
            api_key="test-key",
            model="gemini-test",
            temperature=0.5,
            stream=True,
        )

        self.assertEqual("".join(result), "hello")
        self.models.generate_content_stream.assert_called_once_with(
            model="gemini-test",
            contents="[USER]: Say hello\n",
            config={"temperature": 0.5},
        )


if __name__ == "__main__":
    unittest.main()
