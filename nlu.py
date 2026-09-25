import spacy
from typing import Dict, Any

class JaguarNLU:
    def __init__(self):
        # Load English NLP model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Fallback if model isn't loaded yet
            import os
            os.system("python -m spacy download en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        # Define our "Intent Map"
        # Mapping intents to keywords for classification
        self.intent_keywords = {
            "LIGHTS_ON": ["light", "brighten", "turn on the lights"],
            "LIGHTS_OFF": ["dark", "turn off", "lights off"],
            "TEMPERATURE_SET": ["temperature", "heat", "cool", "degrees"],
            "MUSIC_PLAY": ["music", "play", "song", "spotify"],
            "SYSTEM_STATUS": ["status", "battery", "health", "how are you"],
            "OPEN_APP": ["open", "launch", "start"],
            "CLOSE_APP": ["close", "stop", "exit", "quit"],
        }

    def preprocess(self, text: str) -> str:
        """Clean the input text."""
        return text.lower().strip()

    def get_intent(self, text: str) -> str:
        """Classify the user's goal."""
        for intent, keywords in self.intent_keywords.items():
            if any(keyword in text for keyword in keywords):
                return intent
        return "UNKNOWN_INTENT"

    def extract_slots(self, text: str) -> Dict[str, Any]:
        """Extract entities (dates, numbers, locations)."""
        doc = self.nlp(text)
        slots = {}

        for ent in doc.ents:
            # e.g., "Set temperature to 22 degrees" -> {'CARDINAL': '22'}
            slots[ent.label_] = ent.text

        return slots

    def parse(self, user_input: str) -> Dict[str, Any]:
        """The main pipeline."""
        clean_text = self.preprocess(user_input)
        intent = self.get_intent(clean_text)
        slots = self.extract_slots(clean_text)

        return {
            "original": user_input,
            "intent": intent,
            "slots": slots,
            "confidence": 1.0 if intent != "UNKNOWN_INTENT" else 0.0
        }

# --- Testing the Jaguar NLU ---
if __name__ == "__main__":
    jaguar = JaguarNLU()

    test_phrases = [
        "Alexa, turn on the lights",
        "Set the temperature to 24 degrees",
        "Play some jazz music",
        "What is the system status?",
        "Open notepad",
        "Close calculator"
    ]

    for phrase in test_phrases:
        result = jaguar.parse(phrase)
        print(f"Input: {phrase} \nResult: {result}\n{'-'*30}")
