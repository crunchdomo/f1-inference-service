"""Append predictions to logs/predictions.jsonl (one JSON object per line) and read
recent ones back. Written from the worker; the file lives on a Docker volume.
"""

import json
import os
import threading

LOG_PATH = os.environ.get("PREDICTION_LOG", "logs/predictions.jsonl")
_lock = threading.Lock()


def log_prediction(entry: dict) -> None:
    try:
        os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
        line = json.dumps(entry)
        with _lock, open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception as exc:  # logging shouldn't break a prediction
        print(f"[prediction_log] write failed: {exc}")


def read_recent(limit: int = 20) -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        lines = f.readlines()
    out = []
    for line in lines[-limit:]:
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out
