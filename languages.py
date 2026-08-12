"""
Supported languages for Jaguar AI (voice recognition, TTS, and LLM
reply language).

- "sr_code"   -> locale passed to speech_recognition's Google Web
                 Speech API when transcribing spoken input.
- "gtts_code" -> language code for gTTS synthesis. English is left as
                 None so speaker.py keeps using the faster, offline
                 pyttsx3 engine instead of an online gTTS call.
"""

from typing import Dict, Optional

LANGUAGES: Dict[str, Dict] = {
    "English": {"sr_code": "en-US", "gtts_code": None},
    "Hindi":   {"sr_code": "hi-IN", "gtts_code": "hi"},
    "Telugu":  {"sr_code": "te-IN", "gtts_code": "te"},
    "Tamil":   {"sr_code": "ta-IN", "gtts_code": "ta"},
    "Kannada": {"sr_code": "kn-IN", "gtts_code": "kn"},
}

DEFAULT_LANGUAGE = "English"


def get_sr_code(language: str) -> str:
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])["sr_code"]


def get_gtts_code(language: str) -> Optional[str]:
    return LANGUAGES.get(language, LANGUAGES[DEFAULT_LANGUAGE])["gtts_code"]


def list_languages():
    return list(LANGUAGES.keys())