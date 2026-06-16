import pyttsx3
import speech_recognition as sr


class SpeechEngine:
    def __init__(self):
        self.engine = pyttsx3.init()

        self.engine.setProperty(
            "rate",
            180
        )

        self.engine.setProperty(
            "volume",
            1.0
        )

        voices = self.engine.getProperty("voices")

        if voices:
            self.engine.setProperty(
                "voice",
                voices[0].id
            )

        self.recognizer = sr.Recognizer()

    def speak(self, text):
        print(f"JAGUAR: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        try:
            with sr.Microphone() as source:
                print("Listening...")

                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=1
                )

                audio = self.recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=10
                )

            command = self.recognizer.recognize_google(
                audio
            )

            print("USER:", command)

            return command.lower()

        except:
            return ""