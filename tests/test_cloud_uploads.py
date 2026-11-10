import unittest

from file_reader import extract_text_bytes
from jaguar_core.automation.browser import BrowserAutomation


class CloudUploadProcessingTests(unittest.TestCase):
    def test_text_uploads_are_extracted_from_bytes(self):
        self.assertEqual(
            extract_text_bytes("notes.txt", b"stored only in cloud"),
            "stored only in cloud",
        )

    def test_browser_profile_is_ephemeral(self):
        browser = BrowserAutomation(headless=True)
        browser.close()
        with self.assertRaisesRegex(ValueError, "Persistent local browser"):
            BrowserAutomation(user_data_dir="local-browser-profile")


if __name__ == "__main__":
    unittest.main()
