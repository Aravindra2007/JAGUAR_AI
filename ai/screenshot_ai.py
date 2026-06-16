import pyautogui
import easyocr
from pathlib import Path


class ScreenshotAI:
    def __init__(self):
        self.reader = easyocr.Reader(
            ["en"]
        )

        Path(
            "memory/screenshots"
        ).mkdir(
            parents=True,
            exist_ok=True
        )

    def capture(self):
        path = (
            "memory/screenshots/"
            "screen.png"
        )

        image = pyautogui.screenshot()

        image.save(path)

        return path

    def extract_text(self):
        image = self.capture()

        result = self.reader.readtext(
            image,
            detail=0
        )

        return "\n".join(result)