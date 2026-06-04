"""Load the model and run a single prediction. Shared by the Celery task and the
sync endpoint so the logic lives in one place."""

import os

import joblib
import pandas as pd

MODEL_PATH = os.environ.get("MODEL_PATH", "model/model.pkl")

_model = None
_dnf_lookup = {}
_dnf_fallback = 0.0
_driver_form = {}
_team_form = {}
_global_form = 10.0


def load() -> None:
    global _model, _dnf_lookup, _dnf_fallback, _driver_form, _team_form, _global_form
    artifact = joblib.load(MODEL_PATH)
    _model = artifact["model"]
    _dnf_lookup = artifact["circuit_dnf_rate"]
    _dnf_fallback = artifact["global_dnf_rate"]
    _driver_form = artifact["driver_form"]
    _team_form = artifact["team_form"]
    _global_form = artifact["global_form"]


def predict_one(grid: int, driver: str, constructor: str, circuit: str, season: int) -> dict:
    if _model is None:
        load()

    grid_val = 20 if grid == 0 else grid  # pit-lane start -> back of grid
    dnf_rate = _dnf_lookup.get(circuit, _dnf_fallback)

    # Form features are server-side lookups (the caller doesn't supply them) — we
    # know each driver's/team's recent form from history.
    row = pd.DataFrame([{
        "grid": grid_val,
        "season": season,
        "circuit_dnf_rate": dnf_rate,
        "driver_form": _driver_form.get(driver, _global_form),
        "team_form": _team_form.get(constructor, _global_form),
        "driver": driver,
        "constructor": constructor,
        "circuit": circuit,
    }])
    # predict_proba returns [P(no podium), P(podium)] — we want the second.
    proba = float(_model.predict_proba(row)[0][1])

    return {
        "podium_probability": round(proba, 3),
        "podium_likely": bool(proba >= 0.5),
        "circuit_dnf_rate": round(dnf_rate, 3),
    }
