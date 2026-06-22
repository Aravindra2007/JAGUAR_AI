import pyttsx3

engine = pyttsx3.init()

engine.setProperty("rate", 170)
engine.setProperty("volume", 1.0)

voices = engine.getProperty("voices")

# Male voice (change to voices[1] if you prefer female)
engine.setProperty("voice", voices[0].id)


def speak(text):
    print("Jaguar:", text)
    engine.say(text)
    engine.runAndWait()