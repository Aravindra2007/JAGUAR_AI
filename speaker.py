
import os
import tempfile
import pyttsx3

from languages import get_gtts_code

# ---------------------------------------------------------------
# English -> pyttsx3 (offline, fast, works with the default SAPI5
# voice). Hindi/Telugu/Tamil/Kannada -> gTTS, since most Windows
# machines don't ship a SAPI5 voice for them. gTTS needs internet;
# if that call fails we fall back to pyttsx3 rather than staying
# silent.
# ---------------------------------------------------------------


def _speak_pyttsx3(text):
    engine = pyttsx3.init()
    engine.setProperty("rate", 170)
    engine.say(text)
    engine.runAndWait()


def _speak_gtts(text, lang_code):
    from gtts import gTTS
    from playsound import playsound

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)

        gTTS(text=text, lang=lang_code).save(tmp_path)
        playsound(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def speak(text, language="English"):

    if not text:
        return

    gtts_code = get_gtts_code(language)

    try:
        if gtts_code:
            _speak_gtts(text, gtts_code)
        else:
            _speak_pyttsx3(text)

    except Exception as e:
        print(f"Speaker error ({language}): {e}")
        if gtts_code:
            try:
                _speak_pyttsx3(text)  # last-resort fallback
            except Exception as e2:
                print(f"Speaker fallback error: {e2}")