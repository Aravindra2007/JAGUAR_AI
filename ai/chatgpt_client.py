from openai import OpenAI
from core.settings import OPENAI_KEY


class ChatGPTClient:
    def __init__(self):
        self.client = None

        if OPENAI_KEY:
            self.client = OpenAI(
                api_key=OPENAI_KEY
            )

    def available(self):
        return self.client is not None

    def ask(self, messages):
        if not self.client:
            raise RuntimeError(
                "OpenAI API key not configured."
            )

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages
        )

        return (
            response
            .choices[0]
            .message
            .content
        )