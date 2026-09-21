"""
Jaguar AI — Plan Executor.

Walks a Plan produced by the planner one step at a time, dispatching
each step to either the browser automation, system automation, or the
LLM itself (for "speak" / "done" / answer-generation steps). Returns
a structured execution report so the agent loop can store results,
decide whether to keep going, and feed progress back to the UI.

This is intentionally single-shot - if a step fails, the executor
records the failure and moves on rather than blocking forever.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .planner import Plan, PlanStep
from .automation import BrowserAutomation, SystemAutomation
from . import memory
from llm_client import ask, LLMError


@dataclass
class StepReport:
    step_id: int
    action: str
    description: str
    ok: bool
    message: str
    elapsed: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "description": self.description,
            "ok": self.ok,
            "message": self.message,
            "elapsed": round(self.elapsed, 3),
            "data": self.data,
        }


@dataclass
class ExecutionReport:
    goal: str
    started_at: float
    finished_at: float
    steps: List[StepReport] = field(default_factory=list)
    summary: str = ""
    ok: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed": round(self.finished_at - self.started_at, 3),
            "ok": self.ok,
            "summary": self.summary,
            "steps": [s.to_dict() for s in self.steps],
        }


# ---------------------------------------------------------------
# Executor
# ---------------------------------------------------------------

class PlanExecutor:
    """Carries out a Plan step by step. Reuses one browser instance
    per execution to keep Playwright overhead low."""

    def __init__(
        self,
        *,
        headless_browser: bool = False,
        llm_provider: str = "OpenAI",
        llm_api_key: str = "",
        llm_model: str = "",
        llm_temperature: float = 0.3,
        ollama_host: Optional[str] = None,
    ):
        self.headless_browser = headless_browser
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.ollama_host = ollama_host

        self.browser = BrowserAutomation(headless=headless_browser)
        self.system = SystemAutomation()

    def close(self):
        try:
            self.browser.close()
        except Exception:
            pass

    # ----------------------------------------
    # Public API
    # ----------------------------------------

    def run(self, plan: Plan) -> ExecutionReport:
        started = time.time()
        report = ExecutionReport(goal=plan.goal, started_at=started, finished_at=started)

        for step in plan.steps:
            t0 = time.time()
            sr = self._run_step(step, report)
            sr.elapsed = time.time() - t0
            report.steps.append(sr)
            if not sr.ok and step.action in ("open_website", "search", "apply_jobs"):
                # Record but keep going - later steps may still produce useful output.
                report.ok = False
            if step.action == "done":
                break

        report.finished_at = time.time()
        report.summary = self._summarize(report)
        return report

    # ----------------------------------------
    # Step dispatch
    # ----------------------------------------

    def _run_step(self, step: PlanStep, report: ExecutionReport) -> StepReport:
        action = step.action.lower()

        if action == "open_website":
            res = self.browser.open_website(step.target or "")
            return StepReport(step.id, action, step.description, res.ok,
                              res.message, data=res.data)

        if action == "search":
            res = self.browser.search(step.target or step.description, engine="google")
            return StepReport(step.id, action, step.description, res.ok,
                              res.message, data=res.data)

        if action == "search_jobs":
            params = step.params or {}
            res = self.browser.search_jobs_linkedin(
                query=step.target or step.description,
                location=params.get("location", ""),
                max_results=int(params.get("count", 10) or 10),
            )
            jobs = (res.data or {}).get("jobs") or []
            memory.log_result(
                kind="job_search",
                title=f"{step.target or step.description}",
                detail=f"Found {len(jobs)} job(s)",
            )
            return StepReport(step.id, action, step.description, res.ok,
                              res.message, data=res.data)

        if action == "filter_jobs":
            # The browser automation already returns relevance-tagged
            # results in search_jobs. This step is a pass-through that
            # narrows them by user preferences; we approximate that by
            # filtering out roles without a company / title.
            prior_jobs: List[Dict[str, Any]] = []
            for prev in reversed(report.steps):
                if prev.action == "search_jobs" and prev.data.get("jobs"):
                    prior_jobs = prev.data["jobs"]
                    break
            filtered = [
                j for j in prior_jobs
                if (j.get("title") or "").strip() and (j.get("company") or "").strip()
            ]
            return StepReport(step.id, action, step.description, True,
                              f"Filtered to {len(filtered)} role(s).",
                              data={"jobs": filtered})

        if action == "generate_answers":
            # Use the LLM to draft 3-4 short answers to common
            # application questions.
            defaults = {
                "why_this_role": "I want to grow my skills in this area and contribute to real work.",
                "about_me": "I am a motivated learner with hands-on project experience.",
                "notice_period": "Immediately available.",
                "expected_salary": "Open to discussion, focused on learning.",
            }
            try:
                messages = [
                    {"role": "system",
                     "content": ("You are Jaguar helping the user apply to jobs. "
                                 "Given the goal, return JSON with short answers "
                                 "for: why_this_role, about_me, notice_period, "
                                 "expected_salary. Keep each answer under 200 chars.")},
                    {"role": "user",
                     "content": f"Goal: {report.goal}. Respond with JSON only."},
                ]
                reply = ask(
                    self.llm_provider, messages,
                    api_key=self.llm_api_key, model=self.llm_model,
                    temperature=self.llm_temperature, stream=False,
                    ollama_host=self.ollama_host,
                )
                parsed = _try_parse_json(reply or "")
                if parsed:
                    defaults.update({k: str(v) for k, v in parsed.items()})
            except (LLMError, Exception):
                pass
            return StepReport(step.id, action, step.description, True,
                              "Drafted answers.", data={"answers": defaults})

        if action == "apply_jobs":
            params = step.params or {}
            max_apps = max(1, min(50, int(params.get("max", 5))))
            prior_jobs: List[Dict[str, Any]] = []
            answers: Dict[str, str] = {}
            for prev in reversed(report.steps):
                if prev.action == "filter_jobs" and prev.data.get("jobs"):
                    prior_jobs = prev.data["jobs"]
                if prev.action == "generate_answers" and prev.data.get("answers"):
                    answers = prev.data["answers"]
            prior_jobs = prior_jobs[:max_apps]
            applied: List[Dict[str, Any]] = []
            for job in prior_jobs:
                r = self.browser.apply_to_listing(job, answers)
                applied.append({
                    "job": job,
                    "applied": r.ok,
                    "message": r.message,
                    "steps_walked": (r.data or {}).get("steps_walked", 0),
                })
                memory.log_result(
                    kind="job_application",
                    title=(job.get("title") or "Untitled role"),
                    detail=f"{job.get('company') or 'Unknown'} - {job.get('url') or ''}",
                    status=("applied" if r.ok else "attempted"),
                )
            return StepReport(step.id, action, step.description,
                              bool(applied), f"Attempted {len(applied)} application(s).",
                              data={"applications": applied})

        if action == "fill_form":
            params = step.params or {}
            fields = params.get("fields") if isinstance(params, dict) else None
            if not fields:
                # Accept flat dicts too
                fields = {k: str(v) for k, v in params.items() if k != "fields"}
            res = self.browser.fill_form(fields or {})
            return StepReport(step.id, action, step.description, res.ok,
                              res.message, data=res.data)

        if action in ("click", "press", "type", "wait", "screenshot"):
            return self._dispatch_desktop(step)

        if action == "speak":
            return StepReport(step.id, action, step.description, True,
                              "Speak step recorded.", data={"text": step.target or step.description})

        if action == "store_results":
            return StepReport(step.id, action, step.description, True,
                              "Results were logged by per-step calls.")

        if action == "done":
            return StepReport(step.id, action, step.description, True,
                              step.description or "Done.")

        return StepReport(step.id, action, step.description, False,
                          f"Unknown action '{step.action}'.")

    def _dispatch_desktop(self, step: PlanStep) -> StepReport:
        a = step.action.lower()
        if a == "click":
            params = step.params or {}
            x = params.get("x"); y = params.get("y")
            res = self.system.click(x=int(x) if x is not None else None,
                                    y=int(y) if y is not None else None)
            return StepReport(step.id, a, step.description, res.ok, res.message, data=res.data)
        if a == "press":
            res = self.system.press(step.target or "enter")
            return StepReport(step.id, a, step.description, res.ok, res.message, data=res.data)
        if a == "type":
            res = self.system.type_text(step.target or step.description)
            return StepReport(step.id, a, step.description, res.ok, res.message, data=res.data)
        if a == "wait":
            secs = float((step.params or {}).get("seconds", 1))
            res = self.system.wait(secs)
            return StepReport(step.id, a, step.description, res.ok, res.message, data=res.data)
        if a == "screenshot":
            res = self.browser.screenshot(step.target or "screenshot.png")
            return StepReport(step.id, a, step.description, res.ok, res.message, data=res.data)
        return StepReport(step.id, a, step.description, False, "Unhandled desktop action.")

    # ----------------------------------------
    # Summary
    # ----------------------------------------

    def _summarize(self, report: ExecutionReport) -> str:
        ok_count = sum(1 for s in report.steps if s.ok)
        total = len(report.steps)
        last_msg = report.steps[-1].message if report.steps else ""
        return f"{ok_count}/{total} steps OK. {last_msg}".strip()


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _try_parse_json(text: str):
    if not text:
        return None
    try:
        # Look for fenced json first
        import re
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
    except Exception:
        return None
    return None
