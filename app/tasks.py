"""The async predict task. Loads the model once per worker at startup and logs
every prediction."""

import datetime
import time

from celery.signals import worker_process_init

from app import predictor
from app.celery_app import celery_app
from app.prediction_log import log_prediction


@worker_process_init.connect
def preload_model(**kwargs) -> None:
    t0 = time.perf_counter()
    predictor.load()
    print(f"[startup] model loaded in {(time.perf_counter() - t0) * 1000:.0f} ms")


@celery_app.task(name="predict", bind=True)
def predict(self, grid: int, driver: str, constructor: str, circuit: str, season: int) -> dict:
    result = predictor.predict_one(grid, driver, constructor, circuit, season)

    log_prediction({
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_id": self.request.id,
        "input": {"grid": grid, "driver": driver, "constructor": constructor,
                  "circuit": circuit, "season": season},
        "output": result,
    })
    return result
