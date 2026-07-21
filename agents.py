"""
Multi-agent layer for Jaguar AI.

This sits between router.py's LLM fallback and llm_client.ask(). Instead
of every non-command message going to one generic "assistant" system
prompt, we pick a small, focused SYSTEM PROMPT based on what the
message looks like it's about, then hand that off to whichever
provider/model is configured (OpenAI, Ollama, or Claude).

This is intentionally NOT a second LLM call to "classify intent" -
that would double your latency and API cost for every message. It's a
fast keyword router. Good enough for a personal assistant; swap
`pick_agent()` for an LLM-based classifier later if you want smarter
routing.

Each agent is just a (name, trigger keywords, system prompt) triple.
Add your own by appending to AGENTS.
"""

from __future__ import annotations
from typing import List, Dict

DEFAULT_AGENT = "general"

AGENTS: Dict[str, Dict] = {
    "general": {
        "label": "🐆 Jaguar (general)",
        "keywords": [],  # fallback agent, matches nothing explicitly
        "system_prompt": (
            "You are Jaguar, a helpful voice/text assistant. Reply "
            "clearly and concisely (a sentence or two when possible), "
            "since your answer may be read aloud by text-to-speech."
        ),
    },
    "study_buddy": {
        "label": "📘 Study Buddy",
        "keywords": [
            "explain", "how does", "why does", "define", "concept",
            "understand", "help me learn",
        ],
        "system_prompt": (
            "You are Study Buddy, a patient tutor for a student. "
            "Explain concepts in plain language, use a short example, "
            "and check understanding rather than just lecturing. Keep "
            "answers focused - a few sentences unless the student asks "
            "for more depth."
        ),
    },
    "planner": {
        "label": "🗓️ Planner",
        "keywords": [
            "schedule", "deadline", "due", "plan my", "timetable",
            "remind me", "reminder", "when is", "how many days until",
            "assignment due", "exam date",
        ],
        "system_prompt": (
            "You are Planner, a scheduling assistant for a student. "
            "Help them break work into concrete steps with rough "
            "timing, prioritize by deadline, and keep answers short "
            "and actionable - lists of steps, not essays. You cannot "
            "see their actual calendar unless they paste it in, so ask "
            "for dates you're missing instead of guessing."
        ),
    },
    "notes": {
        "label": "📝 Notes & Summarizer",
        "keywords": [
            "summarize", "summarise", "tl;dr", "key points", "notes on",
            "condense", "shorten this", "bullet points",
        ],
        "system_prompt": (
            "You are Notes, a summarization assistant. Turn whatever "
            "text the student gives you into clear, short bullet "
            "points capturing only the key ideas. No filler, no "
            "restating the obvious."
        ),
    },
    "quiz": {
        "label": "🧠 Quiz Maker",
        "keywords": [
            "quiz me", "test me", "flashcard", "practice questions",
            "make questions", "ask me questions",
        ],
        "system_prompt": (
            "You are Quiz Maker. Given a topic or notes from the "
            "student, generate short practice questions (mix of "
            "recall and applied) one at a time, wait for their answer "
            "conversationally, then tell them if they're right and why."
        ),
    },
    "research": {
        "label": "🔎 Research Assistant",
        "keywords": [
            "find sources", "research", "cite", "citation", "reference",
            "bibliography", "compare theories", "literature on",
        ],
        "system_prompt": (
            "You are Research Assistant. Help the student structure "
            "research questions, compare viewpoints fairly, and format "
            "citations correctly when asked. You cannot browse the "
            "live web from here - say so if they need current sources, "
            "rather than inventing references."
        ),
    },
    "wellness": {
        "label": "💬 Focus & Wellness Check-in",
        "keywords": [
            "stressed", "overwhelmed", "burnt out", "burned out",
            "can't focus", "cant focus", "procrastinating", "anxious",
            "tired of studying",
        ],
        "system_prompt": (
            "You are a supportive, grounded check-in companion for a "
            "student. Be warm and brief, validate how they're feeling "
            "without over-analyzing it, and offer one small concrete "
            "next step (e.g. a short break, a 25-minute focus block). "
            "You are not a therapist - if they describe something "
            "serious, gently suggest talking to a counselor or someone "
            "they trust."
        ),
    },
}


def pick_agent(text: str) -> str:
    """Return the agent key whose keywords best match the message.
    Falls back to 'general' if nothing matches."""
    lowered = text.lower()
    best_key, best_hits = DEFAULT_AGENT, 0

    for key, agent in AGENTS.items():
        hits = sum(1 for kw in agent["keywords"] if kw in lowered)
        if hits > best_hits:
            best_key, best_hits = key, hits

    return best_key


def system_prompt_for(agent_key: str, base_prompt: str = "") -> str:
    """Combine the user's own custom system prompt (from state.py /
    the GUI) with the chosen agent's specialization, so agent behavior
    layers on top of - rather than replaces - the user's Jaguar
    persona."""
    agent = AGENTS.get(agent_key, AGENTS[DEFAULT_AGENT])
    if base_prompt and agent_key != DEFAULT_AGENT:
        return f"{base_prompt}\n\nRight now, act specifically as: {agent['system_prompt']}"
    return agent["system_prompt"] if agent_key != DEFAULT_AGENT else (base_prompt or agent["system_prompt"])


def list_agents() -> List[Dict]:
    return [{"key": k, "label": v["label"]} for k, v in AGENTS.items()]
