# ---------------------------------
# Jaguar AI - Shared State
# ---------------------------------
# Single source of truth for status/text/history, the current LLM
# configuration, the logged-in user, whether Jaguar is speaking right
# now, and any pending file/image attachment context. Flask (app.py),
# Streamlit (streamlit_app.py), the voice listener thread
# (listener.py), and the command router (router.py) all read and
# write through here.

import os
import threading

_lock = threading.Lock()

_current_status = "Idle"
_current_text = "Welcome to Jaguar AI"
_history = []
_muted = False

# ---------------------------------
# Speaking state (for the Stop button)
# ---------------------------------
_is_speaking = False


def set_speaking(speaking: bool):
    global _is_speaking
    with _lock:
        _is_speaking = bool(speaking)


def is_speaking() -> bool:
    with _lock:
        return _is_speaking


# ---------------------------------
# Logged-in user (set by auth.py on login/logout)
# ---------------------------------
# The voice listener thread has no Flask request context, so it can't
# see flask_login's current_user. Login/logout mirrors the id here so
# voice-originated exchanges can still be saved to MySQL under the
# right account.

_current_user_id = None
_current_username = None


def set_current_user(user_id, username):
    global _current_user_id, _current_username
    with _lock:
        _current_user_id = user_id
        _current_username = username


def get_current_user_id():
    with _lock:
        return _current_user_id


def get_current_username():
    with _lock:
        return _current_username


# ---------------------------------
# Pending attachment (uploaded file/image context)
# ---------------------------------
# When a user uploads a document or image via /upload, we stash its
# extracted text/summary here. The router prepends it to the *next*
# message so "read this and summarize it" style requests work whether
# the follow-up came from typing or from voice.

_pending_attachment = None


def set_pending_attachment(context_text: str):
    global _pending_attachment
    with _lock:
        _pending_attachment = context_text


def get_and_clear_pending_attachment():
    global _pending_attachment
    with _lock:
        value = _pending_attachment
        _pending_attachment = None
        return value


# ---------------------------------
# LLM configuration
# ---------------------------------
# Used by router.py whenever a typed/spoken command doesn't match one
# of the built-in commands - instead of "Sorry Sir, I didn't
# understand", the text is handed to the LLM.

DEFAULT_SYSTEM_PROMPT = (
    "You are Jaguar, a helpful voice assistant running on the user's "
    "computer. Reply clearly and concisely (a sentence or two when "
    "possible), since your answer may be read aloud by text-to-speech."
)

_llm_config = {
    "enabled": True,
    "provider": "OpenAI",          # "OpenAI", "Claude (Anthropic)", "Gemini", or "Ollama (local)"
    "api_key": "",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "ollama_host": "",
    # --- Tool-use (Phase 1, Anthropic only) ---
    "tools_enabled": False,
    "workspace_dir": os.path.expanduser("~"),
    "reminders_path": "reminders.json",
}

# Pending confirmation envelopes keyed by uuid token. Both UI surfaces
# (Streamlit button, voice listener) need to find a pending action to
# either approve or deny; the executor stores one here until the user
# responds, then pops it.
_pending_confirmations = {}

DEFAULT_LANGUAGE = "English"
_language = DEFAULT_LANGUAGE


def set_language(language):
    global _language
    with _lock:
        _language = language


def get_language():
    with _lock:
        return _language


def set_status(status):
    global _current_status
    with _lock:
        _current_status = status


def set_text(text):
    global _current_text
    with _lock:
        _current_text = text


def add_history(user_text, assistant_text):
    with _lock:
        _history.append({
            "user": user_text,
            "assistant": assistant_text
        })


def clear_history():
    with _lock:
        _history.clear()


def get_status():
    with _lock:
        return _current_status, _current_text


def get_history():
    with _lock:
        return list(_history)


def set_muted(muted):
    global _muted
    with _lock:
        _muted = bool(muted)


def is_muted():
    with _lock:
        return _muted


def set_llm_config(**kwargs):
    """Update one or more LLM settings (provider, api_key, model,
    temperature, system_prompt, ollama_host, enabled, tools_enabled,
    workspace_dir, reminders_path)."""
    with _lock:
        _llm_config.update(kwargs)


def get_llm_config():
    with _lock:
        return dict(_llm_config)


# ---------------------------------
# Pending confirmations (tool-use)
# ---------------------------------

def push_pending_confirmation(token, envelope):
    with _lock:
        _pending_confirmations[token] = envelope


def pop_pending_confirmation(token):
    with _lock:
        return _pending_confirmations.pop(token, None)


def peek_pending_confirmation(token):
    with _lock:
        envelope = _pending_confirmations.get(token)
        return dict(envelope) if envelope is not None else None
