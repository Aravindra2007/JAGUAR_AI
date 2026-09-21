"""
Optional helper that mounts the FastAPI mobile API inside the existing
Flask app. Run via:

    python api/router_bridge.py

Or import `attach_mobile_api(app)` from your own Flask startup to
expose /mobile/* without spinning up a second process.
"""

from __future__ import annotations

import os
import sys

# Make project root importable when this file is run directly.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from a2wsgi import ASGIMiddleware
from werkzeug.middleware.dispatcher import DispatcherMiddleware


def attach_mobile_api(flask_app, fastapi_app=None):
    """Mount the FastAPI app at /mobile inside the given Flask app.

    Useful for single-process deployments (Render free tier, Fly
    single container, local dev). For larger deployments, run the
    FastAPI app standalone with `uvicorn api.mobile_api:app`.
    """
    if fastapi_app is None:
        from api.mobile_api import app as fastapi_app
    flask_app.wsgi_app = DispatcherMiddleware(
        flask_app.wsgi_app,
        {"/mobile": ASGIMiddleware(fastapi_app)},
    )
    return flask_app


def main():
    import uvicorn
    from api.mobile_api import app as fastapi_app

    host = os.getenv("JAGUAR_API_HOST", "0.0.0.0")
    port = int(os.getenv("JAGUAR_API_PORT", "8000"))
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
