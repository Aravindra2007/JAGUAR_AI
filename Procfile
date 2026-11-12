# Procfile — PaaS (Railway / Fly / Heroku-style) launch.
#
# `web` is the public HTTP service. The WSGI entrypoint mounts the
# FastAPI app under /mobile so both interfaces share the platform port.

web: JAGUAR_ENV=production gunicorn --bind 0.0.0.0:$PORT --workers ${WORKERS:-1} --threads 2 --timeout 120 wsgi:app
