"""
Text-to-speech for Jaguar AI, with a real Stop button.

The original version used pyttsx3.runAndWait() (blocks until finished,
un-interruptible) and the `playsound` package for gTTS (also blocking,
no way to cut it off mid-sentence). Both meant clicking "Stop" only
stopped *future* speech - anything already playing kept talking.

This version:
  - keeps ONE persistent pyttsx3 engine so `engine.stop()` called from
    another thread actually interrupts runAndWait() in the speaking
    thread (this is the documented, supported way to stop pyttsx3).
  - uses pygame.mixer for gTTS playback instead of playsound, polling
    in small slices so a stop request is honored within ~100ms instead
    of waiting for the whole clip to finish.
  - tracks "is speaking" in state.py so the GUI can show a speaking
    indicator and disable/enable the Stop button intelligently.
"""

import os
import tempfile
import threading

import pyttsx3

from languages import get_gtts_code
import state

_engine_lock = threading.Lock()
_engine = None

_stop_event = threading.Event()
_mixer_ready = False


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = pyttsx3.init()
            _engine.setProperty("rate", 170)
        return _engine


def _ensure_mixer():
    global _mixer_ready
    if not _mixer_ready:
        import pygame
        pygame.mixer.init()
        _mixer_ready = True


def stop_speaking():
    """Interrupt whatever is currently being spoken, immediately."""
    _stop_event.set()

    try:
        engine = _get_engine()
        engine.stop()
    except Exception:
        pass

    try:
        if _mixer_ready:
            import pygame
            pygame.mixer.music.stop()
    except Exception:
        pass

    state.set_speaking(False)


def _speak_pyttsx3(text):
    engine = _get_engine()
    engine.say(text)
    engine.runAndWait()


def _speak_gtts(text, lang_code):
    from gtts import gTTS
    import pygame

    _ensure_mixer()

    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(tmp_fd)

        gTTS(text=text, lang=lang_code).save(tmp_path)

        pygame.mixer.music.load(tmp_path)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if _stop_event.is_set():
                pygame.mixer.music.stop()
                break
            pygame.time.wait(100)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def speak(text, language="English"):

    if not text:
        return

    _stop_event.clear()
    gtts_code = get_gtts_code(language)

    state.set_speaking(True)
    try:
        if gtts_code:
            _speak_gtts(text, gtts_code)
        else:
            _speak_pyttsx3(text)

    except Exception as e:
        print(f"Speaker error ({language}): {e}")
        if gtts_code and not _stop_event.is_set():
            try:
                _speak_pyttsx3(text)  # last-resort fallback
            except Exception as e2:
                print(f"Speaker fallback error: {e2}")
    finally:
        state.set_speaking(False)


def speak_async(text, language="English"):
    """Fire-and-forget version so callers (e.g. Flask routes) don't
    block the HTTP response while Jaguar talks."""
    threading.Thread(target=speak, args=(text, language), daemon=True).start()
