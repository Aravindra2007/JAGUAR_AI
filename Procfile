# Procfile — PaaS (Render / Railway / Fly / Heroku-style) launch.
#
# `web` is the public HTTP service. We've combined the Flask GUI and
# the FastAPI mobile API into one process by mounting the FastAPI
# app inside Flask at /mobile. If you prefer two separate services,
# duplicate this block and swap the module for `api.mobile_api:app`
# running under uvicorn (see render.yaml for the multi-service shape).

web: gunicorn --bind 0.0.0.0:$PORT --workers ${WORKERS:-2} --threads 2 --timeout 120 wsgi:app
api: gunicorn --bind 0.0.0.0:$API_PORT --workers ${API_WORKERS:-2} --worker-class uvicorn.workers.UvicornWorker api.mobile_api:app
