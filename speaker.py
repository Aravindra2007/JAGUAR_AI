import pyttsx3

# ---------------------------------------------------------------
# pyttsx3 on Windows (SAPI5) tends to freeze when the same engine
# instance is reused across calls or threads - COM objects are bound
# to the thread that created them, and calling .stop() on an engine
# that hasn't started speaking yet can hang instead of returning.
#
# The reliable fix is to create a fresh engine for every utterance
# and never call .stop() on it. This costs a small amount of startup
# overhead per call (~0.1-0.3s) but avoids the freeze entirely.
# ---------------------------------------------------------------


def speak(text):

    if not text:
        return

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)

        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        print(f"Speaker error: {e}")
