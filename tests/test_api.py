from fastapi.testclient import TestClient

from app import celery_app as celery_module
from app.main import app

client = TestClient(app)

VALID = {"grid": 1, "driver": "hamilton", "constructor": "mercedes",
         "circuit": "silverstone", "season": 2023}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_predict_returns_task_id(monkeypatch):
    # Don't need Redis for this — just check the API queues a job and hands back an id.
    class FakeTask:
        id = "fake-123"

    monkeypatch.setattr(celery_module.celery_app, "send_task", lambda *a, **k: FakeTask())
    r = client.post("/predict", json=VALID)
    assert r.status_code == 200
    assert r.json()["task_id"] == "fake-123"


def test_unknown_driver_is_rejected():
    r = client.post("/predict", json={**VALID, "driver": "not_a_real_driver"})
    assert r.status_code == 422


def test_predict_sync_runs_the_model():
    r = client.post("/predict-sync", json=VALID)
    assert r.status_code == 200
    assert 1 <= r.json()["predicted_position"] <= 20
