# JAGUAR AI — Deployment Guide

Jaguar is built to deploy in many shapes. Pick whichever matches your infrastructure.

## 1. Docker (recommended)

```bash
docker compose up --build
```

That brings up the Jaguar container, exposing the Flask GUI on `http://localhost:5000` and the standalone FastAPI mobile API on `http://localhost:8000` (Swagger UI at `/docs`, ReDoc at `/redoc`). Authentication and persistence use Firebase/Firestore and Supabase; Compose does not start MySQL.

Set `JAGUAR_SECRET_KEY` to a cryptographically random value before starting Compose. Production startup fails if it is missing. Firebase credentials should be supplied through environment variables or a mounted file, not copied into the image.

To run the container alone:

```bash
docker build -t jaguar-ai .
docker run --rm -p 5000:5000 -p 8000:8000 \
  -e JAGUAR_SECRET_KEY=your-generated-secret \
  -e FIREBASE_PROJECT_ID=your-project-id \
  -e FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}' \
  -e OPENAI_API_KEY=sk-... \
  jaguar-ai
```

`deploy/start.sh` boots both services inside the container, gracefully shuts down on SIGTERM, and is the `CMD` of the Dockerfile.

## 2. Railway / Heroku-style PaaS

`Procfile` declares one public web process. The Flask GUI and FastAPI API are served on the platform's assigned `$PORT`; FastAPI routes are mounted under `/mobile`:

* `web` — Flask GUI and FastAPI mobile API via Gunicorn

Configure `JAGUAR_SECRET_KEY` and Firebase credentials in the platform's environment settings.

`fly.toml` is included for Fly.io users; it runs the Flask and FastAPI services on separate internal ports.

## 3. Bare Linux VPS

```bash
git clone <your-repo> /opt/jaguar
cd /opt/jaguar
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium          # optional, for the autonomous agent
cp .env.example .env && nano .env    # fill in secrets
```

Then use either:

* **systemd** — copy `deploy/systemd.service` to `/etc/systemd/system/jaguar.service`, edit paths, `systemctl enable --now jaguar`. Healthcheck URL: `http://127.0.0.1:5000/health`.
* **nginx + gunicorn** — copy `deploy/nginx.conf` to `/etc/nginx/sites-enabled/jaguar`, run `gunicorn --config deploy/gunicorn.conf.py wsgi:app` behind it.

## 4. Windows / local dev

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python app.py             # Flask GUI + voice listener (existing flow)
# or
uvicorn api.mobile_api:app --reload   # mobile API only
# or
deploy\start.bat           # Waitress + Uvicorn (production-like)
```

## Environment variables

See `.env.example`. Configure:

* `JAGUAR_SECRET_KEY` for session signing; it is mandatory in production.
* Firebase credentials for account authentication and Firebase-backed persistence.
* An LLM provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`) or a running `OLLAMA_HOST` to use LLM features.

## Health checks

| Service | URL              | Auth |
|---------|------------------|------|
| Flask GUI | `/health`      | No  |
| FastAPI   | `/health`      | No  |

Both are JSON `{ "status": "ok", ... }`. Container orchestrators can poll them.

## Production notes

* `gunicorn` runs the Flask GUI in production (`wsgi:app`) and mounts FastAPI at `/mobile` on PaaS. Docker/VPS startup runs `uvicorn` separately as `api.mobile_api:app`.
* The Flask service uses one worker by default because application state, the voice listener, and pending confirmations are process-local. Scale out only after moving those states to shared storage.
* Long-running autonomous goals should run in `background=true` mode and be polled via `/autonomous/<job_id>` (Flask) or `/task/{job_id}` (FastAPI).
* The browser automation requires Chromium. Install it once with `playwright install chromium`.
* Tesseract is required only if you use OCR on uploaded images. The Dockerfile installs it by default.
* The image is ~1.5 GB on disk because of Whisper + Playwright + Chromium. Slim it down by removing `openai-whisper` and setting `PLAYWRIGHT_BROWSERS=0` if you don't need those features.
