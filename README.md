# F1 podium-probability predictor

![CI](https://github.com/crunchdomo/f1-inference-service/actions/workflows/ci.yml/badge.svg)

A small async ML service that predicts the **chance an F1 driver finishes on the
podium** (top 3), given their starting grid position, team, the circuit, and the
season. I built it to get hands-on with the FastAPI + Celery + Redis stack and the
practical side of serving a model: don't block the web server, and don't reload the
model on every request.

The prediction runs on a Celery worker rather than inside the request, so the API
stays responsive. Redis sits in between as the job queue. Everything comes up with
`docker compose up`.

## Running it

```bash
docker compose up --build
```

The model trains during the image build (from a committed CSV of past results), so
there's nothing to set up first.

Submit a prediction and poll for the result:

```bash
curl -X POST localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"grid":3,"driver":"hamilton","constructor":"mercedes","circuit":"silverstone","season":2023}'
# {"task_id":"..."}

curl localhost:8000/result/<task_id>
# {"status":"SUCCESS","result":{"podium_probability":0.76,"podium_likely":true,...}}
```

If you'd rather skip the polling, `POST /predict-sync` runs the model inline and
returns the answer directly. That's fine here because the model is fast; the async
path above is the one you'd want for a slow model or for batches. Unknown driver,
team, or circuit ids are rejected with a 422 rather than a silent wrong answer.

`/options` lists the driver/team/circuit ids you can use. There's interactive docs
at `/docs`, a prediction history at `/history`, and a Flower dashboard at `:5555`
for watching tasks go through (login `admin` / `admin` by default — override with
`FLOWER_USER` / `FLOWER_PASSWORD`).

## Tests

```bash
pip install -r requirements-dev.txt
python -m app.train   # builds the model the tests need
pytest
```

There's a small suite: a model quality gate (held-out ROC-AUC must stay above 0.85),
API checks (valid request, bad input is rejected, the sync path works), and the
core logic. It runs in CI on every push (see the badge above).

## How it works

Four services in `docker-compose.yml`:

- `api` — FastAPI. Takes the request, puts a job on the queue, returns a task id.
  Doesn't touch the model.
- `worker` — Celery. Pulls jobs, runs the model, writes the result back.
- `redis` — the job queue, and where results are stored until you fetch them.
- `flower` — task dashboard.

`api` and `worker` are the same image run with different commands.

One thing I spent time on: the worker loads the model once at startup (in a
`worker_process_init` hook) instead of on every request. The first version reloaded
it from disk each time — about 600ms cold, and even once the file was cached it
still re-deserialized the model every call. Loading it once drops the per-request
cost to zero. It barely matters for a model this small, but it's the kind of thing
that bites once the model is large.

More on why each piece is here, and the alternatives, in [WHY.md](./WHY.md).

## Load test

`python load_test.py 1000` fires 1000 predictions at the API and times how long
they take. On my machine the API accepted all 1000 in ~2s and stayed responsive —
the queue absorbs the burst instead of the web server blocking, which is the whole
point of the async design. The workers then drained them at ~290 predictions/s.

One honest finding: scaling to three worker services *didn't* speed it up. The task
is CPU-bound, and a single worker already runs one process per core, so it saturates
the machine; adding more processes just added contention. More throughput here means
more cores or machines, not more workers on the same box. The queue's job —
decoupling and buffering the burst — holds either way.

## The model

A RandomForest **classifier** in a one-hot pipeline, trained on race results from
2014–2024 pulled from the Jolpica/Ergast API. It outputs the **probability of a
podium** (top-3 finish) from grid, driver, team, circuit, season, and a per-circuit
historical DNF rate.

It's a probability on purpose: F1 is noisy (crashes, failures, weather), so a
calibrated "70% chance" is a more honest output than a single hard prediction.
On held-out data it gets **ROC-AUC ~0.93** (ranks who's likely to podium well) and
a **Brier score ~0.07** (the probabilities are reasonably calibrated). Grid position
does most of the work, as you'd expect.

I left out actual weather, pit stops, and tyre data even though they'd help, because
you only know those after the race — training on them would be leakage. The data
pipeline, the leakage reasoning, and the feature roadmap are in [MODEL.md](./MODEL.md).

## Prediction log

Every prediction is appended to `logs/predictions.jsonl` (one JSON object per line)
by the worker, with the inputs, outputs, and a timestamp. It's on a Docker volume,
so it survives restarts, and you can read it back at `/history`.

## Layout

```
app/
  main.py           FastAPI endpoints
  predictor.py      load model + run one prediction (shared by task and sync)
  tasks.py          the Celery predict task
  celery_app.py     Celery / Redis config
  train.py          trains the model
  data_prep.py      fetches the F1 data
  prediction_log.py prediction logging
tests/              pytest suite (model gate, api, logic)
data/f1_results.csv committed so the build is reproducible offline
Dockerfile
docker-compose.yml
.github/workflows/  CI
```

Regenerate the dataset with `python app/data_prep.py`.

## Production notes

A few small hardening choices, since "runs on my machine" isn't the bar:

- The container runs as a **non-root user** (`appuser`) — install and training happen
  as root at build time, the running process doesn't.
- **Flower is behind basic auth** — it's an admin dashboard, so it isn't left open.
- **Redis has a health check**, and the api/worker wait for it to be *ready*
  (`condition: service_healthy`), not just *started*.
- A **`.dockerignore`** keeps the build context small and out of the image.
