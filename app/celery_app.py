"""Celery app, shared by the API (which sends tasks) and the workers (which run them)."""

import os

from celery import Celery

# Redis: db 0 = broker (job queue), db 1 = result backend (finished results).
BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "inference",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["app.tasks"],  # import tasks so they get registered on the worker
)

# Report a STARTED state while a task runs, so /result can distinguish
# "running" from "not picked up yet".
celery_app.conf.update(task_track_started=True)
