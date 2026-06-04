"""Load the model and run a single prediction. Shared by the Celery task and the
sync endpoint so the logic lives in one place."""

import os

import joblib
import pandas as pd

MODEL_PATH = os.environ.get("MODEL_PATH", "model/model.pkl")

_model = None
_dnf_lookup = {}
_dnf_fallback = 0.0


def load() -> None:
    global _model, _dnf_lookup, _dnf_fallback
    artifact = joblib.load(MODEL_PATH)
    _model = artifact["model"]
    _dnf_lookup = artifact["circuit_dnf_rate"]
    _dnf_fallback = artifact["global_dnf_rate"]


def predict_one(grid: int, driver: str, constructor: str, circuit: str, season: int) -> dict:
    if _model is None:
        load()

    grid_val = 20 if grid == 0 else grid  # pit-lane start -> back of grid
    dnf_rate = _dnf_lookup.get(circuit, _dnf_fallback)

    row = pd.DataFrame([{
        "grid": grid_val,
        "season": season,
        "circuit_dnf_rate": dnf_rate,
        "driver": driver,
        "constructor": constructor,
        "circuit": circuit,
    }])
    raw = float(_model.predict(row)[0])

    return {
        "predicted_position": int(max(1, min(20, round(raw)))),  # clamp to 1..20
        "raw_prediction": round(raw, 2),
        "circuit_dnf_rate": round(dnf_rate, 3),
    }
