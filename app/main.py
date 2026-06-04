"""FastAPI app. Takes requests, sends them to Celery, returns a task id to poll."""

import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import predictor
from app.celery_app import celery_app
from app.prediction_log import read_recent

app = FastAPI(title="F1 Podium-Probability Predictor")

# Allow a browser frontend (v0 / Vercel / localhost) to call the API. Defaults to
# all origins for dev; set CORS_ORIGINS (comma-separated) to restrict in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Categories + metrics written by train.py at build time; powers /options.
META_PATH = os.path.join(os.path.dirname(os.environ.get("MODEL_PATH", "model/model.pkl")), "metadata.json")
try:
    with open(META_PATH) as f:
        METADATA = json.load(f)
except FileNotFoundError:
    METADATA = {"metrics": {}, "options": {}, "n_rows": 0}


class PredictRequest(BaseModel):
    grid: int          # 1 = pole, 0 = pit-lane start
    driver: str        # driver id, e.g. "max_verstappen" (see /options)
    constructor: str   # team id, e.g. "red_bull"
    circuit: str       # circuit id, e.g. "monza"
    season: int        # year, e.g. 2023


def validate(req: PredictRequest) -> None:
    """Reject ids the model hasn't seen, instead of silently returning a guess."""
    opts = METADATA.get("options", {})
    for field in ("driver", "constructor", "circuit"):
        valid = opts.get(field, [])
        value = getattr(req, field)
        if valid and value not in valid:
            raise HTTPException(422, f"unknown {field} '{value}' — see /options")
    seasons = METADATA.get("seasons", [])
    if seasons and req.season not in seasons:
        raise HTTPException(422, f"season must be {min(seasons)}–{max(seasons)} — see /options")


@app.post("/predict")
def submit_prediction(req: PredictRequest) -> dict:
    """Async: queue the job, return a task_id to poll. Use this for slow models or batches."""
    validate(req)
    task = celery_app.send_task("predict", kwargs=req.model_dump())
    return {"task_id": task.id}


@app.post("/predict-sync")
def predict_sync(req: PredictRequest) -> dict:
    """Sync: run the model inline and return the answer. Fine when the model is fast
    (like this one). The async path above is for when it isn't."""
    validate(req)
    return predictor.predict_one(**req.model_dump())


@app.get("/result/{task_id}")
def get_result(task_id: str) -> dict:
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }


@app.get("/options")
def options() -> dict:
    return {
        "metrics": METADATA.get("metrics", {}),
        "trained_on_rows": METADATA.get("n_rows", 0),
        "features": METADATA.get("features", []),
        "seasons": METADATA.get("seasons", []),
        "drivers": METADATA.get("options", {}).get("driver", []),
        "constructors": METADATA.get("options", {}).get("constructor", []),
        "circuits": METADATA.get("options", {}).get("circuit", []),
    }


@app.get("/history")
def history(limit: int = 20) -> dict:
    records = read_recent(limit)
    return {"count": len(records), "predictions": records}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
