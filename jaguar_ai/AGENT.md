# JAGUAR AI — Autonomous Voice-Based AI Agent

> Production-ready, deployment-friendly, multi-LLM, voice + text
> desktop AI assistant with an autonomous task-planning agent, a
> long-term vector memory, configurable personality, browser + system
> automation, and a mobile-ready FastAPI backend.

This file is the entry point to the Jaguar AI v2 extension. The existing
GUI (`app.py`, `templates/`, `streamlit_app.py`) is preserved exactly;
the new capabilities are additive and opt-in.

---

## What's new in v2

| Capability | Where it lives | What it does |
|---|---|---|
| **Task planner** | `jaguar_core/planner.py` | Decomposes free-form goals into an ordered list of steps. Uses the configured LLM, with a keyword-based fallback. |
| **Long-term vector memory** | `jaguar_core/memory.py` | Short-term chat window plus persistent semantic memory (FAISS → Chroma → in-memory). Stores user preferences, every chat turn, and every task result. Powers "do like last time". |
| **Personality engine** | `jaguar_core/personality.py` | Composes a system prompt from user tone / style / language preferences. Layered on top of the existing specialist agents. |
| **Browser automation** | `jaguar_core/automation/browser.py` | Playwright wrapper: open URLs, search, fill forms, click, screenshot, with `webbrowser` fallback so the system still works without Playwright. |
| **System automation** | `jaguar_core/automation/system.py` | PyAutoGUI wrapper: type, click, hotkey, clipboard, app launching. |
| **Plan executor** | `jaguar_core/executor.py` | Walks a plan step-by-step, dispatches each action to the right automation backend, collects structured results. |
| **Autonomous mode** | `jaguar_core/autonomous.py` | Given a goal ("apply to 10 internships"), plans, executes, stores results, returns a summary. Runs sync or in the background with a pollable job id. |
| **Mobile-ready backend** | `api/mobile_api.py` | FastAPI app with `/chat`, `/voice`, `/task`, `/task/{id}`, `/tasks`, `/memory/recall`, `/preferences`, `/tts`, `/health`. |

The new endpoints are also exposed inside the existing Flask GUI at `/autonomous`, `/autonomous/<job_id>`, `/personality`, `/memory/recall`, `/memory/results`, and `/health`.

---

## Quickstart

```bash
git clone <your-repo> jaguar_ai && cd jaguar_ai
cp .env.example .env
# edit .env: set JAGUAR_DB_*, OPENAI_API_KEY (or other provider key)
pip install -r requirements.txt
playwright install chromium          # optional, for browser automation

# Existing GUI + voice listener
python main.py                       # then open http://127.0.0.1:5000

# Mobile-ready API (Swagger at /docs, ReDoc at /redoc)
uvicorn api.mobile_api:app --reload  # then open http://127.0.0.1:8000/docs
```

For a one-shot autonomous goal (e.g. apply to internships):

```bash
curl -X POST http://127.0.0.1:8000/task \
  -H 'Content-Type: application/json' \
  -d '{"goal": "Apply to 10 machine learning internships", "background": false}'
```

Or in Python:

```python
from api.mobile_api import app  # FastAPI app
from fastapi.testclient import TestClient
client = TestClient(app)
r = client.post("/task", json={"goal": "Apply to 10 internships", "background": False})
print(r.json())
```

---

## Architecture

```
                ┌──────────────────────────────┐
                │        Existing GUI           │
                │  app.py (Flask)               │
                │  streamlit_app.py             │
                │  listener.py (voice thread)   │
                │  speaker.py (TTS)             │
                └──────────────┬────────────────┘
                               │
                  ┌────────────┴──────────────┐
                  │                           │
        ┌─────────▼─────────┐      ┌──────────▼──────────┐
        │  /chat, /voice,   │      │  /autonomous,       │
        │  /task, /memory,  │      │  /personality,      │
        │  /preferences,    │      │  /memory/*,         │
        │  /tts, /health    │      │  /health            │
        │  (FastAPI)        │      │  (Flask)            │
        └─────────┬─────────┘      └──────────┬──────────┘
                  │                           │
                  └─────────────┬─────────────┘
                                │
                ┌───────────────▼────────────────┐
                │      jaguar_core (new)         │
                │                                │
                │  planner ──┐                   │
                │  memory ───┼──► executor       │
                │  personality ┘                 │
                │       │                        │
                │       ├──► automation/browser  │
                │       └──► automation/system   │
                │                                │
                │       └──► autonomous runner   │
                └────────────────┬───────────────┘
                                 │
                ┌────────────────▼───────────────┐
                │     llm_client (existing)       │
                │  OpenAI / Claude / Gemini /     │
                │  Ollama + tool-use loop         │
                └─────────────────────────────────┘
```

---

## Deployment

See `deploy/README.md` for the full guide. Short version:

* **Docker**: `docker compose up --build`
* **Render**: push this repo, click "New Blueprint Instance", pick `render.yaml`
* **Fly.io**: `fly launch --copy-config && fly deploy`
* **Railway / Heroku-style**: `Procfile` is included
* **Bare VPS**: `deploy/systemd.service` + `deploy/nginx.conf` + `deploy/gunicorn.conf.py`
* **Windows**: `deploy/start.bat`

The image is hardened for production: gunicorn for the Flask GUI, uvicorn for the FastAPI app, health checks at `/health`, graceful SIGTERM shutdown via `deploy/start.sh`.

---

## Voice

`listener.py` keeps its existing continuous-listening loop (Google STT + pyttsx3/gTTS). The mobile API exposes `/voice` (Whisper transcription + chat) and `/tts` (Edge-TTS → gTTS → pyttsx3 fallback, returns base64 audio) so a Flutter / React Native client can speak and hear Jaguar without needing a local Python install.

The wake-word "Hey Jaguar" is honoured by the existing `wakeword.py` and continues to gate the microphone loop on the desktop GUI. Mobile clients can implement their own wake-word on-device.

---

## File map (new files only)

```
jaguar_ai/
├── jaguar_core/
│   ├── __init__.py
│   ├── memory.py                # short + long-term memory, vector index, prefs
│   ├── personality.py           # tone / style / language → system prompt
│   ├── planner.py               # LLM step decomposition + JSON validation
│   ├── executor.py              # walks a plan, dispatches to automation
│   ├── autonomous.py            # autonomous goal runner + job tracking
│   └── automation/
│       ├── __init__.py
│       ├── browser.py           # Playwright + webbrowser fallback
│       └── system.py            # PyAutoGUI wrapper
│
├── api/
│   ├── __init__.py
│   ├── mobile_api.py            # FastAPI app: /chat /voice /task /tts ...
│   └── router_bridge.py         # mount FastAPI inside Flask (single process)
│
├── deploy/
│   ├── start.sh                 # container entrypoint
│   ├── start.bat                # windows equivalent
│   ├── gunicorn.conf.py         # production WSGI config
│   ├── nginx.conf               # reference reverse proxy
│   ├── systemd.service          # systemd unit
│   └── README.md                # full deployment guide
│
├── wsgi.py                      # production WSGI entrypoint
├── Dockerfile                   # production image (Flask + FastAPI)
├── docker-compose.yml           # MySQL + Jaguar local stack
├── Procfile                     # PaaS launch
├── render.yaml                  # Render blueprint
├── fly.toml                     # Fly.io config
├── .dockerignore
├── requirements.txt             # updated with new deps
├── .env.example                 # updated with new env vars
└── jaguar_ai/AGENT.md           # ← you are here
```

---

## License

Released under the same MIT license as the existing project.
