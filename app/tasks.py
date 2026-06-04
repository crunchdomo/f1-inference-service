"""The predict task. The model is loaded once per worker at startup and reused,
rather than reloaded on every request."""

import datetime
import os
import time

import joblib
import pandas as pd
from celery.signals import worker_process_init

from app.celery_app import celery_app
from app.prediction_log import log_prediction

MODEL_PATH = os.environ.get("MODEL_PATH", "model/model.pkl")

_model = None
_dnf_lookup = {}
_dnf_fallback = 0.0


def _load() -> None:
    global _model, _dnf_lookup, _dnf_fallback
    artifact = joblib.load(MODEL_PATH)
    _model = artifact["model"]
    _dnf_lookup = artifact["circuit_dnf_rate"]
    _dnf_fallback = artifact["global_dnf_rate"]


@worker_process_init.connect
def load_model(**kwargs) -> None:
    t0 = time.perf_counter()
    _load()
    print(f"[startup] model loaded in {(time.perf_counter() - t0) * 1000:.0f} ms")


@celery_app.task(name="predict", bind=True)
def predict(self, grid: int, driver: str, constructor: str, circuit: str, season: int) -> dict:
    load_ms = 0.0
    if _model is None:  # fallback if the startup hook didn't run
        t0 = time.perf_counter()
        _load()
        load_ms = (time.perf_counter() - t0) * 1000

    grid_val = 20 if grid == 0 else grid  # pit-lane start -> back of grid
    dnf_rate = _dnf_lookup.get(circuit, _dnf_fallback)

    # The pipeline selects columns by name, so pass a one-row DataFrame.
    row = pd.DataFrame([{
        "grid": grid_val,
        "season": season,
        "circuit_dnf_rate": dnf_rate,
        "driver": driver,
        "constructor": constructor,
        "circuit": circuit,
    }])

    t1 = time.perf_counter()
    raw = float(_model.predict(row)[0])
    predict_ms = (time.perf_counter() - t1) * 1000

    result = {
        "predicted_position": int(max(1, min(20, round(raw)))),  # clamp to 1..20
        "raw_prediction": round(raw, 2),
        "circuit_dnf_rate": round(dnf_rate, 3),
        "model_load_ms": round(load_ms, 2),
        "predict_ms": round(predict_ms, 2),
    }

    log_prediction({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_id": self.request.id,
        "input": {"grid": grid, "driver": driver, "constructor": constructor,
                  "circuit": circuit, "season": season},
        "output": result,
    })
    return result
