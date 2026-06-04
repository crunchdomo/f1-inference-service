# Why this stack

Notes on why each piece is here and what the alternatives were. The short version:
ML inference is slow and bursty, so you don't want to run it inside the web request.
The whole design is about accepting work quickly, running it elsewhere, and letting
the client poll for the result.

## FastAPI — the web layer

Takes the request, validates it, drops a job on the queue, and returns a task id.
It doesn't run the model. Pydantic gives request validation for free, and it's
async-native so the API keeps accepting connections while work happens elsewhere.

Alternatives: Flask works but you'd bolt on libraries for validation, async, and
docs. Django is far too much for a JSON API. Running the model directly in the
route is exactly the blocking problem this design avoids.

## Celery — the task queue

Runs the prediction in a separate worker process. The API hands off a job and moves
on; a pool of workers pulls jobs, runs the model, and stores the result. Web and
compute scale independently. You also get retries, result tracking, and concurrency
without writing any of it yourself.

Alternatives: threads or asyncio don't help with CPU-bound work because of the GIL,
and in-flight work is lost if the API restarts. A hand-rolled Redis queue means
reimplementing Celery (serialization, acks, retries, result storage). SQS + Lambda
works but ties the project to a cloud and hides the parts I wanted to build.

## Redis — broker and result backend

Two roles: the broker is the queue of pending jobs between the API and the workers;
the result backend is where a finished prediction sits until the client fetches it.

Why a broker instead of the API calling a worker directly:

- The API can accept a job even when every worker is busy — it waits in Redis
  instead of being rejected.
- It buffers bursts. 1,000 requests against 4 workers drain at a sustainable rate
  instead of falling over.
- The API doesn't need to know how many workers exist or whether one just died.
- Jobs survive a worker crash, because they live in Redis, not in a process.

Redis specifically because it's in-memory (fast), can be both broker and backend in
one container, and is the standard Celery broker. RabbitMQ is a better pure broker
but heavier, and it can't double as the result backend. A database table as a queue
is slow to poll.

## Docker Compose

The system is several processes that need to talk to each other. Compose defines
that in one file, so `docker compose up` starts the whole thing the same way on any
machine. It also matches the real shape: the API and the worker are separate,
independently scalable services. Kubernetes would be the production answer, but it's
overkill here.

## The model — scikit-learn

A RandomForest in a one-hot pipeline (details in MODEL.md). It's cheap to run, which
is what makes the cold-start cost stand out: the slow part isn't the prediction,
it's loading the model into memory. The worker loads it once at startup instead of
on every request.

## Request flow

```
   Client                FastAPI            Redis (broker)         Celery Worker
     │                     │                     │                     │
     │  POST /predict      │                     │                     │
     │────────────────────▶│                     │                     │
     │                     │  enqueue job        │                     │
     │                     │────────────────────▶│                     │
     │   { task_id }       │                     │   worker picks up    │
     │◀────────────────────│                     │────────────────────▶│
     │                     │                     │                     │ run model
     │                     │                     │   store result      │ (preloaded
     │                     │                     │◀────────────────────│  in memory)
     │  GET /result/{id}   │                     │                     │
     │────────────────────▶│   read result       │                     │
     │                     │────────────────────▶│                     │
     │   { prediction }    │                     │                     │
     │◀────────────────────│                     │                     │
```

The client never waits on the model. It gets a task id immediately and polls for
the answer.
