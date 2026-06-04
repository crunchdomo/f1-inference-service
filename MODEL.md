# The F1 Model — Data, Training, and How It All Fits Together

This documents the F1 finishing-position predictor: where the data comes from, how
it's turned into a model, how that model is served, what it gets right, what it
gets wrong (and *why*), and how weather / pit stops / tyres are handled.

> The **serving architecture** (FastAPI + Celery + Redis + Docker + Flower) is
> documented in [`WHY.md`](./WHY.md). This doc is only about the **model and data layer**.
> That separation is the whole point: we changed the model without touching the
> platform.

---

## 1. What we're predicting

**Input** (a race entry): `grid` position, `driver`, `constructor` (team),
`circuit`, and `season`.
**Output**: predicted **finishing position** (1 = win, 20 = back of the field).

It's a **regression** problem — we predict a number and round it to a grid slot.

---

## 2. The end-to-end flow (how the pieces fit)

```
  data_prep.py          train.py              model.pkl           tasks.py (worker)
  ───────────           ────────              ─────────           ─────────────────
  Jolpica API  ──fetch─▶ f1_results.csv ─train─▶ {pipeline +       ──load──▶ in-memory
  (real F1     (4626    (one-hot + numeric        dnf lookup}       once at startup,
   results)     rows)    + RandomForest)                            serve every request

         build time (baked into Docker image)        │  run time
  ────────────────────────────────────────────────── │ ──────────────────────
                                                      ▼
   Client ─POST /predict {grid,driver,team,circuit,season}─▶ FastAPI ─▶ Redis ─▶ worker
   Client ◀──────────────── {predicted_position} ◀── /result ◀── Redis ◀── result ◀┘
```

Two distinct phases:
- **Build time** (once, when the image is built): `data_prep.py` → CSV →
  `train.py` → `model.pkl`. Baked into the image.
- **Run time** (every request): a Celery worker that already holds the model in
  memory predicts. No training, no disk loads on the hot path.

---

## 3. The data pipeline — `data_prep.py`

- **Source:** the [Jolpica API](https://api.jolpi.ca) — the maintained successor to
  the Ergast F1 database. Free, no auth.
- **What we pull:** every race result for **2014–2024** (turbo-hybrid era). For each
  result: `season, round, circuit, driver, constructor, grid, position, status`.
- **Volume:** **4,626 rows** — 59 drivers, 20 constructors, 32 circuits.
- **Why a committed CSV?** Fetch once locally, commit the CSV, so the Docker build
  trains **offline and reproducibly** — no network dependency mid-build.

---

## 4. Training — `train.py`

### Features — all known BEFORE the race (this matters; see §7 on leakage)

| Feature | Type | What it contributes |
|---|---|---|
| `grid` | numeric | Starting position — by far the strongest signal |
| `season` | numeric | The **era**: distinguishes a driver's rookie car from their title car |
| `circuit_dnf_rate` | numeric | Historical attrition at the track — a **leakage-free proxy for the chaos that weather, reliability, and pit problems cause** |
| `driver`, `constructor`, `circuit` | one-hot | Identities (112 columns after encoding) |

The whole thing is one sklearn **Pipeline** (`ColumnTransformer` one-hot for the
categories + passthrough for the numerics → `RandomForestRegressor`). The API
passes raw values; the pipeline encodes internally. One artifact, no train/serve skew.

### `circuit_dnf_rate` — incorporating "weather & pit stops" honestly

We can't use *this race's* actual weather or pit stops (that's leakage — §7). But
the **consequence** of those things — cars not finishing — is a stable property of
each circuit that we *do* know in advance. Street and weather-prone circuits
(Monaco, Baku, Spa, Singapore) have high historical DNF rates; clean ones (Barcelona)
are low. We compute that rate from history and feed it in.

**Leakage-safe computation:** the rate is derived from the **training split only**,
then mapped onto the held-out test rows — so a race's own outcome never leaks into
the feature it's scored on. (The shipped model recomputes it on all data.)

### Two cleaning decisions

- **`grid = 0`** (pit-lane start) → remapped to **20** (back of grid), at train and
  predict time, so it isn't misread as better than pole.
- **DNFs are kept** with their classified finishing position — they're real, and
  they teach the model that races are noisy.

### Evaluation (held-out 20%)

| | Original (grid + ids) | **+ season + circuit_dnf_rate** |
|---|---|---|
| **MAE** | 3.57 positions | **3.54 positions** |
| **R²** | 0.358 | **0.389** |

The new features measurably raised R² (more variance explained). MAE barely moved,
which is expected — `grid` already carried most of the predictable signal, and the
rest of a race's outcome is genuinely unpredictable.

---

## 5. Serving — `tasks.py` + `main.py`

- The worker **preloads** the artifact once at startup (`worker_process_init`):
  the pipeline **plus** the circuit→DNF-rate lookup. Per-request load cost = 0 ms.
- `predict` fills `circuit_dnf_rate` from the circuit id (a **server-side lookup**,
  not a user input — the caller only supplies the circuit), builds a one-row
  DataFrame, and calls `pipeline.predict()`.
- `POST /predict` validates `{grid, driver, constructor, circuit, season}` and hands
  it to Celery. `GET /options` lists valid ids, seasons, features, and metrics.

---

## 6. What it gets right — and what stays hard

### Right (in-distribution)

Real 2023 scenarios land within a position or two — matching the MAE:

```
  Verstappen P1, Red Bull, Bahrain 2023   -> P2   (actually won)
  Hamilton   P3, Mercedes, Silverstone 23 -> P4   (actually P3)
  Leclerc    P1, Ferrari, Monza 2019      -> P2   (actually won)
  Sargeant   P20, Williams, Bahrain 2023  -> P16  (backmarker, sensible)
```

And sweeping grid for a well-represented case (Hamilton/Mercedes/Silverstone) is
monotonic: grid 1→P1.2, 5→P2.8, 10→P5.7, 15→P8.6.

### Still hard (out-of-distribution) — and why season only partly helped

Ask for **Verstappen on pole at Monza** and it predicts ~P8. Adding `season`
improved this (it was ~P13 before), but didn't fix it — because the problem isn't a
missing feature, it's **structural**:

- Verstappen started pole at Monza exactly **once** in the data (2021 — he crashed).
  "Verstappen + Monza + pole" is a combination that essentially **never happened**.
- **RandomForests can't extrapolate.** For a feature combination it hasn't seen, a
  tree model falls back to the nearest leaves it *has* seen — here, his *typical*
  Monza results (midfield) — and the strong global `grid` signal gets overridden by
  the memorized driver×circuit cell.

This is the honest, important lesson: **more features raise aggregate accuracy, but
no feature lets a tree model reason about combinations outside its training data.**
The genuine fixes are different in kind (see §7) — more data, or a model/encoding
that doesn't memorize sparse cells. A model that *claimed* to nail this OOD case
would be overfitting, not succeeding.

---

## 7. Weather, pit stops, tyres — how they're handled

### The rule that governs all of it: no leakage

> **A feature is only usable if you'd know its value *before* the race.**

| Thing | Verdict | How it's handled |
|---|---|---|
| `grid`, `driver`, `team`, `circuit`, `season` | ✅ pre-race | Used directly |
| **Pit-stop / weather / attrition *chaos*** | ✅ via proxy | `circuit_dnf_rate` — the historical *tendency*, known in advance |
| **This race's actual pit-stop count** | ❌ leakage | An outcome; excluded. (Only the *planned* strategy would be fair, which we don't have.) |
| **This race's actual tyre stints** | ❌ leakage | An outcome; excluded |
| **This race's recorded weather** | ⚠️ forecast only | A *forecast* would be fair (see below); the *recorded* value is post-hoc |

So pit stops and weather **are** represented — through `circuit_dnf_rate`, the
leakage-free signal you'd actually have pre-race — while their post-race actuals are
deliberately kept out to avoid a model that cheats.

### True per-race weather — the one real extension left

To use *this race's* weather legitimately, you'd bring in a **pre-race forecast**
(rain probability, track temp). The data source is the
[FastF1](https://docs.fastf1.dev) library, which exposes recorded session weather
for **2018+**. The build would be:
1. For each race, pull session weather via FastF1 → derive `was_wet` / `track_temp`.
2. Train on recorded weather; at predict time, supply the **forecast** (a mild,
   accepted train/serve gap).

It's a real data-engineering lift (heavier dependency, 2018+ only, slow downloads),
which is why it's scoped as a possible next iteration rather than baked in here.

### Other clean, no-leakage features worth adding next

| Feature | Why it helps | Source |
|---|---|---|
| Qualifying gap (ms off pole) | Finer than integer grid | Jolpica `qualifying` endpoint |
| Recent driver/team form | Captures upgrades / momentum | Rolling mean of prior races (no leakage if shifted) |
