"""
Jaguar AI — Mobile-Ready Backend (FastAPI).

A second HTTP surface, alongside the existing Flask GUI, designed for
mobile clients (Flutter, React Native, SwiftUI, etc.) and for
external integrations. Every endpoint returns JSON.

Endpoints:
  GET  /                     service banner + version
  GET  /health               liveness probe
  POST /chat                 free-form chat (text in, text out)
  POST /voice                transcribe + reply (audio in, text out)
                             (Whisper if installed, else placeholder)
  POST /task                 plan + execute a multi-step goal
  GET  /task/{job_id}        poll an autonomous job
  GET  /tasks                list recent autonomous jobs
  POST /memory/recall        semantic recall over long-term memory
  GET  /preferences          read user preferences
  POST /preferences          update user preferences
  POST /tts                  text-to-speech (returns base64 audio)

The FastAPI app reuses the existing llm_client, personality engine,
planner, executor, and autonomous runner, so behaviour stays
consistent between the GUI and the mobile API.
"""

from __future__ import annotations

import base64
import io
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Reuse existing LLM router + new core modules.
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from llm_client import ask, LLMError  # noqa: E402
import agents  # noqa: E402
import state  # noqa: E402
import db  # noqa: E402
from jaguar_core import memory, personality, planner  # noqa: E402
from jaguar_core.autonomous import (  # noqa: E402
    run_autonomous_goal, get_job, list_jobs,
)


APP_NAME = "Jaguar AI Mobile API"
APP_VERSION = "1.0.0"
_bearer_auth = HTTPBearer(auto_error=False)


def _authenticated_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_auth),
) -> Dict[str, Any]:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(401, "A Firebase ID token is required.")
    try:
        claims = db.verify_firebase_id_token(credentials.credentials)
    except db.DBError as error:
        raise HTTPException(401, str(error)) from error

    email = str(claims.get("email") or "").strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise HTTPException(403, "A verified Firebase email is required.")
    try:
        user = db.get_user_by_email(email)
    except Exception as error:
        raise HTTPException(503, "Jaguar account lookup is unavailable.") from error
    if user is None:
        raise HTTPException(403, "No Jaguar account is linked to this Firebase user.")
    return user


# ---------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------

class LLMConfig(BaseModel):
    provider: str = "OpenAI"
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    ollama_host: Optional[str] = None


class ChatRequest(BaseModel):
    text: str = Field(..., description="User's message.")
    config: Optional[LLMConfig] = None
    history: Optional[List[Dict[str, str]]] = None


class ChatResponse(BaseModel):
    reply: str
    agent: str
    recalled_context: str = ""
    elapsed: float = 0.0


class TaskRequest(BaseModel):
    goal: str = Field(..., description="High-level goal to plan + execute.")
    config: Optional[LLMConfig] = None
    background: bool = True
    headless_browser: bool = False


class TaskResponse(BaseModel):
    job_id: str
    goal: str
    status: str
    plan: Optional[Dict[str, Any]] = None
    report: Optional[Dict[str, Any]] = None
    summary: str = ""
    progress: float = 0.0
    error: Optional[str] = None


class VoiceResponse(BaseModel):
    transcript: str
    reply: str
    agent: str


class RecallRequest(BaseModel):
    query: str
    top_k: int = 5
    kind: Optional[str] = None


class RememberRequest(BaseModel):
    text: str
    kind: str = "project"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    importance: float = 0.5
    approved: bool = False


class MemoryUpdateRequest(BaseModel):
    text: str


class RecallResponse(BaseModel):
    query: str
    entries: List[Dict[str, Any]]


class PreferenceUpdate(BaseModel):
    tone: Optional[str] = None
    communication_style: Optional[str] = None
    language: Optional[str] = None
    name: Optional[str] = None
    interests: Optional[List[str]] = None
    default_search_engine: Optional[str] = None
    wake_word: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    language: str = "English"


class TTSResponse(BaseModel):
    audio_base64: str
    mime: str = "audio/mp3"


# ---------------------------------------------------------------
# App factory
# ---------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description=(
            "Mobile-ready HTTP API for the Jaguar AI agent. Plug a "
            "Flutter / React Native / native mobile client straight in."
        ),
    )

    # Mobile clients will hit this from different origins, so allow
    # CORS everywhere. Tighten in production via env if you care.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routes(app)
    return app


# ---------------------------------------------------------------
# Routes
# ---------------------------------------------------------------

def register_routes(app: FastAPI) -> None:

    @app.get("/")
    def root() -> Dict[str, Any]:
        return {
            "service": APP_NAME,
            "version": APP_VERSION,
            "endpoints": [
                "/health", "/chat", "/voice", "/task",
                "/task/{job_id}", "/tasks",
                "/memory", "/memory/recall", "/preferences",
                "/preferences/tone", "/tts",
            ],
        }

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "time": time.time(),
            "memory_backend": _memory_backend_name(),
        }

    # -------------------------
    # Chat
    # -------------------------

    @app.post("/chat", response_model=ChatResponse)
    def chat(
        req: ChatRequest,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> ChatResponse:
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(400, "Empty text.")

        cfg = req.config or LLMConfig()
        agent_key = agents.pick_agent(text)
        system_prompt = personality.build_system_prompt(
            base_prompt="You are Jaguar, an autonomous voice/text AI assistant.",
            agent_specialization=agents.system_prompt_for(agent_key, ""),
            preferences=memory.get_preferences(user_id=str(user["id"])),
        )
        ctx = memory.recall_context_block(
            text,
            top_k=4,
            user_id=str(user["id"]),
        )
        if ctx:
            system_prompt += f"\n\n{ctx}"

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if req.history:
            for entry in req.history[-10:]:
                if "user" in entry:
                    messages.append({"role": "user", "content": str(entry["user"])})
                if "assistant" in entry:
                    messages.append({"role": "assistant", "content": str(entry["assistant"])})
        messages.append({"role": "user", "content": text})

        t0 = time.time()
        try:
            reply = ask(
                cfg.provider,
                messages,
                api_key=cfg.api_key,
                model=cfg.model,
                temperature=cfg.temperature,
                stream=False,
                ollama_host=cfg.ollama_host,
            )
        except LLMError as e:
            raise HTTPException(502, f"LLM error: {e}")

        reply_text = (reply or "").strip() or "I'm not sure how to respond to that."
        db.save_chat_message(
            str(user["id"]),
            text,
            reply_text,
            source="mobile",
        )

        return ChatResponse(
            reply=reply_text,
            agent=agent_key,
            recalled_context=ctx,
            elapsed=round(time.time() - t0, 3),
        )

    # -------------------------
    # Voice (Whisper STT + LLM)
    # -------------------------

    @app.post("/voice", response_model=VoiceResponse)
    async def voice(
        audio: UploadFile = File(...),
        config: str = Form("{}"),
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> VoiceResponse:
        import json as _json
        try:
            cfg = LLMConfig(**_json.loads(config or "{}"))
        except Exception:
            cfg = LLMConfig()

        data = await audio.read()
        transcript = _transcribe(data)

        # Run the same /chat path on the transcript.
        chat_resp = chat(
            ChatRequest(text=transcript, config=cfg),
            user=user,
        )
        return VoiceResponse(
            transcript=chat_resp.reply and transcript or transcript,
            reply=chat_resp.reply,
            agent=chat_resp.agent,
        )

    # -------------------------
    # Task (autonomous)
    # -------------------------

    @app.post("/task", response_model=TaskResponse)
    def task(
        req: TaskRequest,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> TaskResponse:
        cfg = req.config or LLMConfig()
        job = run_autonomous_goal(
            goal=req.goal,
            llm_provider=cfg.provider,
            llm_api_key=cfg.api_key,
            llm_model=cfg.model,
            llm_temperature=cfg.temperature,
            ollama_host=cfg.ollama_host,
            headless_browser=req.headless_browser,
            background=req.background,
            user_id=str(user["id"]),
        )
        return TaskResponse(
            job_id=job.id, goal=job.goal, status=job.status,
            plan=job.plan.to_dict() if job.plan else None,
            report=job.report.to_dict() if job.report else None,
            summary=job.summary, progress=job.progress, error=job.error,
        )

    @app.get("/task/{job_id}", response_model=TaskResponse)
    def task_status(
        job_id: str,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> TaskResponse:
        job = get_job(job_id, user_id=str(user["id"]))
        if not job:
            raise HTTPException(404, "Unknown job_id.")
        return TaskResponse(
            job_id=job.id, goal=job.goal, status=job.status,
            plan=job.plan.to_dict() if job.plan else None,
            report=job.report.to_dict() if job.report else None,
            summary=job.summary, progress=job.progress, error=job.error,
        )

    @app.get("/tasks")
    def tasks_list(
        limit: int = 50,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        return {
            "jobs": [
                j.to_dict()
                for j in list_jobs(limit=limit, user_id=str(user["id"]))
            ],
        }

    # -------------------------
    # Memory
    # -------------------------

    @app.post("/memory/recall", response_model=RecallResponse)
    def recall(
        req: RecallRequest,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> RecallResponse:
        entries = memory.recall(
            req.query,
            top_k=req.top_k,
            kind=req.kind,
            user_id=str(user["id"]),
        )
        return RecallResponse(
            query=req.query,
            entries=[e.to_dict() for e in entries],
        )

    @app.post("/memory/remember")
    def remember(
        payload: RememberRequest,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        if not payload.approved:
            raise HTTPException(400, "Explicit approval is required.")
        if not payload.text.strip():
            raise HTTPException(400, "Empty text.")
        try:
            entry_id = memory.remember(
                payload.text,
                kind=payload.kind,
                metadata=payload.metadata,
                importance=payload.importance,
                user_id=str(user["id"]),
            )
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return {"id": entry_id, "ok": True}

    @app.get("/memory")
    def memory_list(
        kind: Optional[str] = None,
        limit: int = 100,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        try:
            entries = memory.list_memories(
                user_id=str(user["id"]),
                kind=kind,
                limit=limit,
            )
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return {"entries": [entry.to_dict() for entry in entries]}

    @app.put("/memory/{entry_id}")
    def memory_update(
        entry_id: str,
        payload: MemoryUpdateRequest,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        try:
            updated = memory.update_memory(
                entry_id,
                payload.text,
                user_id=str(user["id"]),
            )
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        if not updated:
            raise HTTPException(404, "Memory not found.")
        return {"ok": True}

    @app.delete("/memory/{entry_id}")
    def memory_delete(
        entry_id: str,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        if not memory.forget(entry_id, user_id=str(user["id"])):
            raise HTTPException(404, "Memory not found.")
        return {"ok": True}

    # -------------------------
    # Preferences
    # -------------------------

    @app.get("/preferences")
    def prefs_get(
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        return memory.get_preferences(user_id=str(user["id"]))

    @app.post("/preferences")
    def prefs_update(
        update: PreferenceUpdate,
        user: Dict[str, Any] = Depends(_authenticated_user),
    ) -> Dict[str, Any]:
        prefs = memory.get_preferences(user_id=str(user["id"]))
        for k, v in update.dict(exclude_none=True).items():
            prefs = memory.update_preference(k, v, user_id=str(user["id"]))
        return prefs

    # -------------------------
    # TTS (returns base64 mp3)
    # -------------------------

    @app.post("/tts", response_model=TTSResponse)
    def tts(req: TTSRequest) -> TTSResponse:
        text = (req.text or "").strip()
        if not text:
            raise HTTPException(400, "Empty text.")
        audio_bytes, mime = _synthesise_speech(text, req.language)
        return TTSResponse(
            audio_base64=base64.b64encode(audio_bytes).decode("ascii"),
            mime=mime,
        )


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _memory_backend_name() -> str:
    """Report the configured persistent-memory provider without probing it."""
    return (
        "supabase"
        if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SECRET_KEY")
        else "unavailable"
    )


def _transcribe(audio_bytes: bytes) -> str:
    """Best-effort Whisper transcription. Falls back to a no-op stub
    with a clear message so the endpoint stays usable when Whisper
    or ffmpeg isn't installed. Audio is decoded in memory."""
    try:
        import numpy as np
        import subprocess
        import whisper  # type: ignore

        decoded = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-i", "pipe:0",
                "-f", "s16le", "-ac", "1",
                "-acodec", "pcm_s16le", "-ar", "16000", "pipe:1",
            ],
            input=audio_bytes,
            capture_output=True,
            check=True,
        )
        samples = (
            np.frombuffer(decoded.stdout, dtype=np.int16)
            .astype(np.float32)
            / 32768.0
        )
        if samples.size == 0:
            return "(transcription unavailable: audio stream was empty)"
        model = whisper.load_model("base")
        result = model.transcribe(samples, fp16=False)
        return (result.get("text") or "").strip()
    except Exception as e:
        return f"(transcription unavailable: {e})"


def _synthesise_speech(text: str, language: str = "English"):
    """Return (bytes, mime). Tries edge-tts first, then gTTS, then
    pyttsx3 (writes a wav)."""
    # edge-tts (offline-friendly once installed, online-required at runtime)
    try:
        import edge_tts  # type: ignore
        import asyncio

        async def _go():
            voice_map = {
                "english": "en-US-AriaNeural",
                "hindi":   "hi-IN-SwaraNeural",
                "telugu":  "te-IN-MohanNeural",
                "tamil":   "ta-IN-ValluvarNeural",
                "spanish": "es-ES-ElviraNeural",
                "french":  "fr-FR-DeniseNeural",
                "german":  "de-DE-KatjaNeural",
            }
            voice = voice_map.get(language.lower(), "en-US-AriaNeural")
            communicate = edge_tts.Communicate(text, voice=voice)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        data = asyncio.run(_go())
        if data:
            return data, "audio/mpeg"
    except Exception:
        pass

    # gTTS fallback
    try:
        from gtts import gTTS  # type: ignore
        from languages import get_gtts_code
        code = get_gtts_code(language) or "en"
        buf = io.BytesIO()
        gTTS(text=text, lang=code).write_to_fp(buf)
        return buf.getvalue(), "audio/mpeg"
    except Exception:
        pass

    # pyttsx3 wav fallback
    try:
        import pyttsx3  # type: ignore
        import wave
        engine = pyttsx3.init()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tmp_path = tf.name
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        with open(tmp_path, "rb") as f:
            data = f.read()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return data, "audio/wav"
    except Exception as e:
        raise HTTPException(500, f"TTS unavailable: {e}")


# ---------------------------------------------------------------
# ASGI app
# ---------------------------------------------------------------

app = create_app()
