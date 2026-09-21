"""
WSGI entrypoint for production servers (gunicorn / waitress / uWSGI).

Production usage:
    gunicorn --bind 0.0.0.0:5000 wsgi:app

Development usage (the existing project entry points still work):
    python main.py           # Flask GUI + voice listener (existing)
    python app.py            # Flask GUI only
    uvicorn api.mobile_api:app   # FastAPI mobile API only
"""

from __future__ import annotations

import os
import sys

# Make sure the project root is on sys.path so relative imports work
# regardless of how the server is launched.
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load .env before anything else so config is consistent.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def create_app():
    """Build and return the Flask app, mounting the FastAPI mobile
    API at /mobile so a single gunicorn process serves both UIs."""
    from app import app as flask_app

    if os.getenv("JAGUAR_MOUNT_MOBILE_API", "1") == "1":
        try:
            from api.router_bridge import attach_mobile_api
            from api.mobile_api import app as fastapi_app
            attach_mobile_api(flask_app, fastapi_app)
        except Exception as e:
            print(f"[wsgi] Mobile API not mounted: {e}")

    return flask_app


# WSGI servers (gunicorn, waitress) look for `app` by default.
app = create_app()
