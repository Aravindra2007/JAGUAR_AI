import threading
import speech_recognition as sr
from core.speaker import speak

WAKE_WORDS = [
    "hey jaguar",
    "hi jaguar",
    "okay jaguar",
    "jaguar"
]

class VoiceThread(threading.Thread):

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.running = True

    def listen(self, recognizer):

        with sr.Microphone() as source:

            recognizer.adjust_for_ambient_noise(source, duration=0.3)

            audio = recognizer.listen(
                source,
                timeout=None,
                phrase_time_limit=6
            )

        return recognizer.recognize_google(audio).lower()

    def run(self):

        r = sr.Recognizer()
        speak("Jaguar Assembling Sir! ")

        while self.running:

            try:

                print("Listening for wake word...")

                query = self.listen(r)

                print("Heard:", query)

                for wake in WAKE_WORDS:

                    if wake in query:

                        command = query.replace(wake, "").strip()

                        # Command already spoken
                        if command:

                            self.callback(command)
                            break

                        # Wake word only
                        speak("Yes, how can I help?")

                        print("Listening for command...")

                        command = self.listen(r)

                        print("Command:", command)

                        self.callback(command)

                        break

            except Exception:
                pass

    def stop(self):
        self.running = False