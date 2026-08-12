# wakeword.py

WAKE_WORDS = [
    "hey jaguar",
    "hi jaguar",
    "hello jaguar",
    "okay jaguar",
    "jaguar"
]


class WakeWordDetector:

    def __init__(self, wake_words=None):
        self.wake_words = wake_words or WAKE_WORDS

    def detect(self, text: str) -> bool:
        """
        Returns True if a wake word is detected.
        """
        if not text:
            return False

        text = text.lower().strip()

        return any(word in text for word in self.wake_words)

    def remove(self, text: str) -> str:
        """
        Removes the wake word from the sentence.

        Example:
        'hey jaguar open google'
        -> 'open google'
        """
        if not text:
            return ""

        text = text.lower().strip()

        for wake in self.wake_words:
            if text.startswith(wake):
                return text.replace(wake, "", 1).strip()

        return text