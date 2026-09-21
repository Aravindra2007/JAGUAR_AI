# ============================================================
# Jaguar AI — production-ready multi-service container image.
# ============================================================
# Builds a single image that runs:
#   1) the Flask GUI on PORT (default 5000), and
#   2) the FastAPI mobile API on API_PORT (default 8000)
#
# Both processes are launched by `deploy/start.sh` and gracefully
# shut down on SIGTERM. Pick whichever one(s) you want to expose to
# the public internet via your hosting platform's port config.
#
# Designed for:
#   - Render      (use render.yaml)
#   - Railway     (auto-detected Procfile)
#   - Fly.io      (fly.toml)
#   - AWS App Runner / ECS / Fargate
#   - Any VPS     (`docker compose up`)
# ============================================================

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=5000 \
    API_PORT=8000 \
    JAGUAR_DB_HOST="" \
    JAGUAR_DB_PORT=3306 \
    JAGUAR_DB_USER=root \
    JAGUAR_DB_PASSWORD="" \
    JAGUAR_DB_NAME=jaguar_ai

# OS deps: build-essential for any wheels that need compiling,
# ffmpeg for Whisper audio, tesseract for OCR on uploads, and the
# usual runtime libs Playwright needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        ffmpeg \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python deps ---------------------------------------------------------
# Copy only requirements first so the Docker layer caches them.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# --- Playwright browsers --------------------------------------------------
# We use Playwright when it's installed, but only download Chromium by
# default to keep the image lean. Set PLAYWRIGHT_BROWSERS=1 in your env
# to trigger the download step.
ARG PLAYWRIGHT_BROWSERS=1
ENV PLAYWRIGHT_BROWSERS=${PLAYWRIGHT_BROWSERS}
RUN if [ "$PLAYWRIGHT_BROWSERS" = "1" ]; then \
        playwright install --with-deps chromium; \
    fi

# --- App ------------------------------------------------------------------
COPY . .

# Persistent, container-local data lives here. In production you'd
# typically mount a volume at /app/jaguar_data and/or use a managed
# database for MySQL.
RUN mkdir -p /app/jaguar_data /app/uploads /app/logs
VOLUME ["/app/jaguar_data", "/app/uploads", "/app/logs"]

EXPOSE 5000 8000

# Healthcheck hits the Flask /health (added in app.py). If you only
# expose the FastAPI API, swap the URL.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health" || exit 1

CMD ["bash", "deploy/start.sh"]
