"""
Jaguar AI — Personality Engine.

Generates the system prompt Jaguar uses for a given user, based on
their stored preferences (tone, communication style, language,
interests). Personality is layered on top of the existing
agents.system_prompt_for() output so it composes with the specialist
agents (Study Buddy, Planner, etc.) without replacing them.

The goal isn't to be clever — it's to keep Jaguar's voice consistent
across chat, voice, the autonomous agent, and the FastAPI mobile
backend, while letting each user tune it once and forget about it.
"""

from __future__ import annotations

from typing import Dict, Optional

from jaguar_core import memory


# Tone presets. Each one is a short paragraph the model is asked to
# embody. They are intentionally short — long system prompts eat
# tokens and don't measurably change behaviour for short replies.
TONE_PRESETS: Dict[str, str] = {
    "friendly": (
        "Speak warmly and with genuine enthusiasm, like a helpful "
        "friend who happens to know a lot. Use contractions, the "
        "occasional light joke is welcome, and keep sentences short "
        "enough to be read aloud easily."
    ),
    "professional": (
        "Speak like a knowledgeable colleague giving a quick, "
        "accurate answer. Avoid slang and filler, prefer precise "
        "language, and structure multi-part replies with light "
        "bullets."
    ),
    "casual": (
        "Be relaxed and conversational. Keep things short, "
        "light, and direct - like texting a smart friend. Use "
        "informal contractions freely."
    ),
    "mentor": (
        "Be a patient, encouraging mentor. Explain the 'why' "
        "alongside the 'how', and end with one concrete next step "
        "the user can take."
    ),
}

STYLE_PRESETS: Dict[str, str] = {
    "concise": "Keep replies tight - 1 to 3 sentences unless the user clearly wants more.",
    "detailed": "Give fuller answers with examples or short lists when helpful.",
}


def _language_directive(language: str) -> str:
    if not language or language.lower() == "english":
        return ""
    return (
        f"\n\nAlways reply in {language}, regardless of the language "
        "the user writes in. Do not mix in English unless the user "
        "explicitly asks you a question in English."
    )


def build_system_prompt(
    base_prompt: str = "",
    *,
    preferences: Optional[Dict] = None,
    agent_specialization: Optional[str] = None,
) -> str:
    """Compose the final system prompt from base + personality +
    agent specialization + language.

    Parameters
    ----------
    base_prompt
        The user-configured base prompt from the LLM settings panel.
    preferences
        User preferences dict (memory.get_preferences()). If None,
        they are loaded fresh.
    agent_specialization
        The specialist agent's system prompt (e.g. Study Buddy),
        layered on top so the agent behaviour survives.
    """
    prefs = preferences or memory.get_preferences()
    tone = (prefs.get("tone") or "friendly").lower()
    style = (prefs.get("communication_style") or "concise").lower()
    language = prefs.get("language") or "English"
    name = prefs.get("name") or ""

    tone_blurb = TONE_PRESETS.get(tone, TONE_PRESETS["friendly"])
    style_blurb = STYLE_PRESETS.get(style, STYLE_PRESETS["concise"])

    parts = [
        base_prompt or "You are Jaguar, a helpful voice/text AI assistant.",
        f"Personality: {tone_blurb}",
        f"Format: {style_blurb}",
    ]
    if name:
        parts.append(f"The user's name is {name}; address them by name when natural.")
    if agent_specialization:
        parts.append(f"Role for this turn: {agent_specialization}")
    parts.append(_language_directive(language).strip())

    return "\n\n".join(p for p in parts if p)


def set_tone(tone: str) -> Dict:
    """Convenience: update the tone preference and return the new set."""
    return memory.update_preference("tone", tone)


def set_style(style: str) -> Dict:
    return memory.update_preference("communication_style", style)


def set_user_name(name: str) -> Dict:
    return memory.update_preference("name", name)


def set_language(language: str) -> Dict:
    return memory.update_preference("language", language)


def available_tones() -> list:
    return sorted(TONE_PRESETS.keys())


def available_styles() -> list:
    return sorted(STYLE_PRESETS.keys())
