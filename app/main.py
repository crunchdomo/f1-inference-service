"""FastAPI app. Takes requests, sends them to Celery, returns a task id to poll."""

import json
import os

from fastapi import FastAPI
from pydantic import BaseModel

from app.celery_app import celery_app
from app.prediction_log import read_recent

app = FastAPI(title="F1 Finishing-Position Predictor")

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


@app.post("/predict")
def submit_prediction(req: PredictRequest) -> dict:
    task = celery_app.send_task("predict", kwargs=req.model_dump())
    return {"task_id": task.id}


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
