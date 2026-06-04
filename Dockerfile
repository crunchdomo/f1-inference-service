# One image, used by BOTH the api and the worker — they only differ by the command
# they run (see docker-compose.yml). That mirrors production: same code artifact,
# deployed as two independently scalable services.

FROM python:3.12-slim

WORKDIR /app

# Where the model lives inside the container. Set as an env var so train.py (build
# time) and tasks.py (run time) both agree on the path.
ENV MODEL_PATH=/app/model/model.pkl

# Install deps first, in their own layer, so changing app code doesn't bust the
# pip cache and force a reinstall on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and the pre-fetched F1 dataset (committed CSV, so the
# build needs no network — data_prep.py was run once, offline, to produce it).
COPY app ./app
COPY data ./data

# Train the model AT BUILD TIME so it's baked into the image. This is what makes
# `docker compose up` a true one-command start — there's nothing to pre-run, no
# volume to mount, no "did you remember to train first?" footgun.
RUN python -m app.train
