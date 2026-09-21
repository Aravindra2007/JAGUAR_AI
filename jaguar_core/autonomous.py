"""
Jaguar AI — Autonomous Mode.

Given a goal like "Apply to 10 internships", this:
  1. Asks the planner to decompose it into steps.
  2. Filters and adapts those steps using user preferences + memory.
  3. Walks them through the plan executor.
  4. Stores every result so the user can ask later "did my apps go?"
  5. Speaks / returns a short summary.

It is intentionally synchronous and conservative - it never claims
success the browser automation didn't actually achieve. Results are
persisted to the SQLite log and to long-term vector memory, so the
agent improves recall across sessions.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .planner import make_plan, Plan
from .executor import PlanExecutor, ExecutionReport, StepReport
from . import memory
from llm_client import ask, LLMError


# ---------------------------------------------------------------
# Active-job tracking
# ---------------------------------------------------------------

_ACTIVE_JOBS: Dict[str, "AutonomousJob"] = {}
_JOBS_LOCK = threading.Lock()


@dataclass
class AutonomousJob:
    id: str
    goal: str
    status: str = "pending"          # pending | running | done | error
    started_at: float = 0.0
    finished_at: float = 0.0
    plan: Optional[Plan] = None
    report: Optional[ExecutionReport] = None
    summary: str = ""
    progress: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed": round(max(self.finished_at, time.time()) - self.started_at, 3)
                        if self.started_at else 0,
            "progress": round(self.progress, 3),
            "summary": self.summary,
            "plan": self.plan.to_dict() if self.plan else None,
            "report": self.report.to_dict() if self.report else None,
            "error": self.error,
        }


def _new_job(goal: str) -> AutonomousJob:
    job_id = f"job_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
    job = AutonomousJob(id=job_id, goal=goal)
    with _JOBS_LOCK:
        _ACTIVE_JOBS[job_id] = job
    return job


def get_job(job_id: str) -> Optional[AutonomousJob]:
    with _JOBS_LOCK:
        return _ACTIVE_JOBS.get(job_id)


def list_jobs(limit: int = 50) -> List[AutonomousJob]:
    with _JOBS_LOCK:
        return sorted(_ACTIVE_JOBS.values(), key=lambda j: j.started_at, reverse=True)[:limit]


def prune_old_jobs(keep_last: int = 50):
    with _JOBS_LOCK:
        jobs = sorted(_ACTIVE_JOBS.values(), key=lambda j: j.started_at, reverse=True)
        for old in jobs[keep_last:]:
            _ACTIVE_JOBS.pop(old.id, None)


# ---------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------

def run_autonomous_goal(
    goal: str,
    *,
    llm_provider: str = "OpenAI",
    llm_api_key: str = "",
    llm_model: str = "",
    llm_temperature: float = 0.3,
    ollama_host: Optional[str] = None,
    headless_browser: bool = False,
    background: bool = False,
) -> AutonomousJob:
    """Plan and execute an autonomous goal.

    Parameters
    ----------
    background
        If True, execute on a daemon thread and return the job
        immediately. The caller can poll `get_job(job_id)` to follow
        progress.
    """
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("Empty goal")

    # Recall anything we've done before that looks similar - the
    # context block is forwarded to the planner so "do like last
    # time" works on a fresh goal.
    ctx = memory.recall_context_block(goal, top_k=4)

    plan = make_plan(
        goal,
        provider=llm_provider,
        api_key=llm_api_key,
        model=llm_model,
        temperature=llm_temperature,
        ollama_host=ollama_host,
        memory_context=ctx or None,
    )
    job = _new_job(goal)
    job.plan = plan
    job.started_at = time.time()

    def _run():
        job.status = "running"
        executor = PlanExecutor(
            headless_browser=headless_browser,
            llm_provider=llm_provider,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            llm_temperature=llm_temperature,
            ollama_host=ollama_host,
        )
        try:
            total = max(1, len(plan.steps))
            report = ExecutionReport(
                goal=goal, started_at=time.time(), finished_at=time.time(),
            )

            for idx, step in enumerate(plan.steps, start=1):
                from .executor import PlanExecutor as _PE
                sr = _run_step_with_progress(executor, step, report, idx, total, job)
                report.steps.append(sr)
                job.progress = idx / total
                if step.action == "done":
                    break

            report.finished_at = time.time()
            report.summary = _summarize(report)
            job.report = report
            job.summary = report.summary
            job.status = "done" if report.ok else "error"
            memory.log_result(
                kind="autonomous_goal",
                title=goal,
                detail=report.summary,
                status=job.status,
            )
        except Exception as e:
            job.status = "error"
            job.error = str(e)
        finally:
            job.finished_at = time.time()
            try:
                executor.close()
            except Exception:
                pass

    if background:
        threading.Thread(target=_run, daemon=True).start()
        return job

    _run()
    return job


def _run_step_with_progress(
    executor: PlanExecutor,
    step,
    report: ExecutionReport,
    idx: int,
    total: int,
    job: AutonomousJob,
) -> StepReport:
    """Wrapper around the executor's _run_step so we can advance the
    job's progress bar after each step."""
    sr = executor._run_step(step, report)
    return sr


def _summarize(report: ExecutionReport) -> str:
    ok_count = sum(1 for s in report.steps if s.ok)
    total = len(report.steps)
    last = report.steps[-1].message if report.steps else ""
    return f"{ok_count}/{total} steps OK. {last}".strip()
