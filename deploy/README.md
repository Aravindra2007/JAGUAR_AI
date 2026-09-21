# JAGUAR AI — Deployment Guide

Jaguar is built to deploy in many shapes. Pick whichever matches your infrastructure.

## 1. Docker (recommended)

```bash
docker compose up --build
```

That brings up the Jaguar container, which uses Firebase/Firestore, exposing the existing Flask GUI on `http://localhost:5000` and the FastAPI mobile API on `http://localhost:8000` (Swagger UI at `/docs`, ReDoc at `/redoc`).

To run the container alone (with an existing MySQL):

```bash
docker build -t jaguar-ai .
docker run --rm -p 5000:5000 -p 8000:8000 \
  -e FIREBASE_PROJECT_ID=your-project-id \
  -e FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}' \
  -e OPENAI_API_KEY=sk-... \
  jaguar-ai
```

`deploy/start.sh` boots both services inside the container, gracefully shuts down on SIGTERM, and is the `CMD` of the Dockerfile.

## 2. Render

`render.yaml` is a Render Blueprint. Click the **Blueprints → New Blueprint Instance** button in Render and point it at this repo; Render reads `render.yaml` and provisions:

* `jaguar-gui`  (Flask GUI, public web service)
* `jaguar-api`  (FastAPI mobile API, public web service)
* `jaguar-db`   (managed MySQL 8)

Set `OPENAI_API_KEY` (and any other provider keys) in the Render dashboard after the first deploy.

## 3. Railway / Fly.io / Heroku-style PaaS

`Procfile` declares two processes. Most platforms auto-detect it:

* `web` — Flask GUI via gunicorn
* `api` — FastAPI mobile API via gunicorn + uvicorn worker

`fly.toml` is included for Fly.io users; `fly launch --copy-config && fly deploy`.

## 4. Bare Linux VPS

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

## 5. Windows / local dev

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python main.py             # Flask GUI + voice listener (existing flow)
# or
uvicorn api.mobile_api:app --reload   # mobile API only
# or
deploy\start.bat           # gunicorn + uvicorn together (production-like)
```

## Environment variables

See `.env.example`. Everything is optional except:

* `JAGUAR_DB_*` (for the existing MySQL persistence)
* `JAGUAR_SECRET_KEY` (Flask session signing)
* At least one LLM provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, or a running `OLLAMA_HOST`)

## Health checks

| Service | URL              | Auth |
|---------|------------------|------|
| Flask GUI | `/health`      | No  |
| FastAPI   | `/health`      | No  |

Both are JSON `{ "status": "ok", ... }`. Container orchestrators can poll them.

## Production notes

* `gunicorn` runs the Flask GUI in production (`wsgi:app`). `uvicorn` runs the FastAPI app standalone (`api.mobile_api:app`).
* Long-running autonomous goals should run in `background=true` mode and be polled via `/autonomous/<job_id>` (Flask) or `/task/{job_id}` (FastAPI).
* The browser automation requires Chromium. Install it once with `playwright install chromium`.
* Tesseract is required only if you use OCR on uploaded images. The Dockerfile installs it by default.
* The image is ~1.5 GB on disk because of Whisper + Playwright + Chromium. Slim it down by removing `openai-whisper` and setting `PLAYWRIGHT_BROWSERS=0` if you don't need those features.
