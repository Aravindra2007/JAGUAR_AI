# gunicorn.conf.py — production WSGI configuration for the Flask GUI.
# Picked up automatically by gunicorn when launched from this dir.
import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", f"0.0.0.0:{os.getenv('PORT', '5000')}")
workers = int(os.getenv("WORKERS", str(min(4, multiprocessing.cpu_count() * 2 + 1))))
threads = int(os.getenv("THREADS", "2"))
timeout = int(os.getenv("TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("KEEPALIVE", "5"))
worker_class = os.getenv("WORKER_CLASS", "sync")  # gthread / gevent / uvicorn.workers.UvicornWorker
accesslog = os.getenv("ACCESS_LOG", "-")
errorlog = os.getenv("ERROR_LOG", "-")
loglevel = os.getenv("LOG_LEVEL", "info")
preload_app = os.getenv("PRELOAD", "1") == "1"
