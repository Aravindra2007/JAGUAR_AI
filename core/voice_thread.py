import threading
import speech_recognition as sr

class VoiceThread(threading.Thread):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.running = True

    def run(self):
        r = sr.Recognizer()

        while self.running:
            with sr.Microphone() as source:
                print("Listening...")
                r.pause_threshold = 1
                audio = r.listen(source)

            try:
                query = r.recognize_google(audio)
                print("You said:", query)
                self.callback(query.lower())

            except:
                continue

    def stop(self):
        self.running = False