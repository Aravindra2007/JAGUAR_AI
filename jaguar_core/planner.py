"""
Jaguar AI — Task Planner.

Converts a free-form user goal ("book train ticket", "apply to 10
internships") into a structured, ordered list of steps that the
executor can carry out one at a time.

The planner is LLM-driven so it adapts to whatever goal the user types
or speaks, but the output is always JSON-shaped and validated before
anything tries to run it. If the model returns something unparsable,
we fall back to a small keyword-based decomposer so the system stays
useful even when the LLM is offline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional

from llm_client import ask, LLMError


# ---------------------------------------------------------------
# Data model
# ---------------------------------------------------------------

@dataclass
class PlanStep:
    """One executable step inside a plan."""
    id: int
    action: str            # e.g. "open_website", "fill_form", "search_jobs"
    description: str       # human-readable sentence for the chat UI
    target: Optional[str] = None   # url, search query, file path, ...
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    goal: str
    steps: List[PlanStep]
    source: str = "llm"   # "llm" or "fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "source": self.source,
            "steps": [s.to_dict() for s in self.steps],
        }


# ---------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = (
    "You are Jaguar, an autonomous task planner. Given a user goal, you "
    "decompose it into a small, ordered list of concrete steps the "
    "assistant can execute one at a time.\n\n"
    "Always reply with ONLY valid JSON - no prose, no markdown fences. "
    "The JSON must match this shape exactly:\n"
    "{\n"
    '  "steps": [\n'
    '    {"action": "open_website",  "description": "...", "target": "https://..."},\n'
    '    {"action": "search",        "description": "...", "target": "search query"},\n'
    '    {"action": "fill_form",     "description": "...", "params": {...}},\n'
    '    {"action": "click",         "description": "...", "target": "button text"},\n'
    '    {"action": "apply_job",     "description": "...", "params": {"site": "linkedin", "role": "..."}},\n'
    '    {"action": "type",          "description": "...", "target": "text to type"},\n'
    '    {"action": "press",         "description": "...", "target": "enter"},\n'
    '    {"action": "wait",          "description": "...", "params": {"seconds": 1}},\n'
    '    {"action": "speak",         "description": "...", "target": "text to say"},\n'
    '    {"action": "done",          "description": "Goal accomplished."}\n'
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Use between 2 and 12 steps. Fewer is better when the goal is simple.\n"
    "- Each step must be independently executable.\n"
    "- For browser actions, prefer open_website, search, fill_form, click, apply_job.\n"
    "- For system actions, prefer type, press, wait, speak.\n"
    "- Always end with a final 'done' step summarising the outcome."
)


def _build_planner_prompt(goal: str, context: Optional[str] = None) -> List[Dict[str, str]]:
    """Build the chat messages we send to the LLM to plan a goal."""
    user_msg = f"Goal: {goal}"
    if context:
        user_msg += f"\n\nRelevant context from memory:\n{context}"
    user_msg += "\n\nRespond with only the JSON plan."
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


# ---------------------------------------------------------------
# Parsing + validation
# ---------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(raw: str) -> Optional[str]:
    """Pull the first JSON object out of an LLM reply (which may be
    wrapped in markdown fences or surrounded by prose)."""
    if not raw:
        return None
    fenced = _JSON_FENCE_RE.search(raw)
    if fenced:
        return fenced.group(1)
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start:end + 1]
    return None


def _coerce_step(idx: int, raw: Dict[str, Any]) -> PlanStep:
    """Turn an LLM-emitted dict into a validated PlanStep, applying
    sane defaults for missing fields."""
    return PlanStep(
        id=idx + 1,
        action=str(raw.get("action", "")).strip().lower() or "unknown",
        description=str(raw.get("description", "")).strip() or f"Step {idx + 1}",
        target=raw.get("target"),
        params=dict(raw.get("params") or {}),
    )


def _parse_llm_json(goal: str, raw: str) -> Plan:
    """Validate that the LLM's reply actually matches our plan schema."""
    blob = _extract_json(raw)
    if not blob:
        raise ValueError("planner response did not contain JSON")

    data = json.loads(blob)
    raw_steps = data.get("steps") or []
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("planner response had no steps")

    steps: List[PlanStep] = []
    for i, item in enumerate(raw_steps[:12]):    # hard cap of 12 steps
        if isinstance(item, dict):
            steps.append(_coerce_step(i, item))

    if not steps:
        raise ValueError("planner returned empty steps")

    return Plan(goal=goal, steps=steps, source="llm")


# ---------------------------------------------------------------
# Keyword fallback
# ---------------------------------------------------------------

# Used when the LLM is offline / fails / returns garbage. Far less
# capable than the LLM path, but keeps the system useful.

def _fallback_plan(goal: str) -> Plan:
    lowered = goal.lower()

    # IRCTC / train
    if any(k in lowered for k in ("train", "irctc", "railway")):
        return Plan(goal=goal, source="fallback", steps=[
            PlanStep(1, "open_website", "Open the IRCTC / MakeMyTrip train search page.",
                     target="https://www.makemytrip.com/railways/"),
            PlanStep(2, "search", "Search for the requested train journey on the page.",
                     target=goal),
            PlanStep(3, "fill_form", "Fill in the source, destination, and date fields.",
                     params={"fields": ["from", "to", "date"]}),
            PlanStep(4, "click", "Click the search button.", target="Search"),
            PlanStep(5, "speak", "Tell the user the available trains.",
                     target="Here are the trains I found."),
            PlanStep(6, "done", "Goal accomplished."),
        ])

    # Job apply
    if any(k in lowered for k in ("job", "internship", "apply", "hire")):
        count = 5
        m = re.search(r"(\d+)\s*(internship|job|application|position)", lowered)
        if m:
            try:
                count = max(1, min(50, int(m.group(1))))
            except ValueError:
                count = 5
        return Plan(goal=goal, source="fallback", steps=[
            PlanStep(1, "open_website", "Open the job search portal.",
                     target="https://www.linkedin.com/jobs/"),
            PlanStep(2, "search_jobs", "Search for relevant roles for the user.",
                     target=goal, params={"count": count}),
            PlanStep(3, "filter_jobs", "Filter roles by location, remote, and relevance."),
            PlanStep(4, "generate_answers", "Draft answers to common application questions."),
            PlanStep(5, "apply_jobs", "Submit applications one by one.",
                     params={"max": count}),
            PlanStep(6, "store_results", "Save every application to the results database.",
                     params={"kind": "job_apply"}),
            PlanStep(7, "speak", "Tell the user how many applications were sent.",
                     target=f"I applied to {count} roles for you."),
            PlanStep(8, "done", "Goal accomplished."),
        ])

    # Generic web search
    if any(k in lowered for k in ("search", "find", "look up", "google")):
        return Plan(goal=goal, source="fallback", steps=[
            PlanStep(1, "open_website", "Open Google search.",
                     target="https://www.google.com"),
            PlanStep(2, "search", "Run the user's search query.",
                     target=goal),
            PlanStep(3, "speak", "Summarise what was found.",
                     target="Here's what I found."),
            PlanStep(4, "done", "Goal accomplished."),
        ])

    # Truly generic - just do a Google search
    return Plan(goal=goal, source="fallback", steps=[
        PlanStep(1, "open_website", "Open Google to look this up.",
                 target="https://www.google.com"),
        PlanStep(2, "search", "Search for the user's request.",
                 target=goal),
        PlanStep(3, "speak", "Speak the result back to the user.",
                 target="I looked that up for you."),
        PlanStep(4, "done", "Goal accomplished."),
    ])


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

def make_plan(
    goal: str,
    *,
    provider: str = "OpenAI",
    api_key: str = "",
    model: str = "",
    temperature: float = 0.3,
    ollama_host: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> Plan:
    """Build a Plan for `goal`. Tries the LLM first, falls back to a
    keyword-based planner if anything goes wrong."""
    goal = (goal or "").strip()
    if not goal:
        return Plan(goal="", steps=[
            PlanStep(1, "speak", "I need a goal to plan for.", target="Please tell me what to do."),
            PlanStep(2, "done", "Nothing to do."),
        ], source="fallback")

    messages = _build_planner_prompt(goal, memory_context)
    try:
        reply = ask(
            provider,
            messages,
            api_key=api_key,
            model=model,
            temperature=temperature,
            stream=False,
            ollama_host=ollama_host,
        )
        if isinstance(reply, str):
            return _parse_llm_json(goal, reply)
        return _fallback_plan(goal)
    except (LLMError, ValueError, json.JSONDecodeError, KeyError, TypeError):
        return _fallback_plan(goal)
    except Exception:
        return _fallback_plan(goal)
