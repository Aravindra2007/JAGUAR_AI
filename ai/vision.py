from ai.screenshot_ai import ScreenshotAI
# from ai.chatgpt_client import ChatGPTClient


class VisionAI:
    def __init__(self):
        self.screen = ScreenshotAI()

    def explain_screen(
        self,
        assistant
    ):
        text = self.screen.extract_text()

        prompt = f"""
        Explain this screen:

        {text}
        """

        return assistant.ask_ai(prompt)