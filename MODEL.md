# The F1 model — data, training, and how it fits together

This documents the podium-probability model: where the data comes from, how it's
trained, how it's served, and what it does and doesn't do.

> The **serving architecture** (FastAPI + Celery + Redis + Docker + Flower) is
> documented in [`WHY.md`](./WHY.md). This doc is only about the **model and data
> layer** — which is the part you can swap without touching the platform.

---

## 1. What it predicts

**Input:** a race entry — `grid` position, `driver`, `constructor` (team),
`circuit`, and `season`.
**Output:** the **probability that the driver finishes on the podium** (top 3).

It's a **classification** problem (podium: yes/no), and the model returns the
probability of "yes" rather than a hard label — because F1 is noisy, and a
calibrated "72% chance" is a more honest, more useful output than a flat
yes/no.

Why probability and not, say, exact finishing position? Predicting an exact
position (`P4.2`) pretends to a precision that doesn't exist in a sport full of
crashes and safety cars. The probability of a meaningful *event* is the right shape
of answer for a noisy outcome.

---

## 2. The end-to-end flow

```
  data_prep.py          train.py              model.pkl           predictor.py
  ───────────           ────────              ─────────           ─────────────
  Jolpica API  ──fetch─▶ f1_results.csv ─train─▶ {classifier +     ──load──▶ in memory,
  (real F1     (4626    (one-hot +              dnf lookup}        serve every request
   results)     rows)    RandomForest)
```

- **Build time** (once, when the image is built): `data_prep.py` → CSV →
  `train.py` → `model.pkl`. Baked into the image.
- **Run time** (every request): a worker holds the model in memory and predicts.

---

## 3. The data — `data_prep.py`

- **Source:** the [Jolpica API](https://api.jolpi.ca), the maintained successor to
  the Ergast F1 database. Free, no auth.
- **What we pull:** every race result for **2014–2024**. For each: `season, round,
  circuit, driver, constructor, grid, position, status`.
- **Volume:** **4,626 rows** — 59 drivers, 20 constructors, 32 circuits.
- **Why a committed CSV?** Fetch once locally, commit it, so the build trains
  **offline and reproducibly**.

---

## 4. Training — `train.py`

### The target
`podium = (position <= 3)` — a 1/0 label. About **15%** of entries are podiums, so
the classes are imbalanced (we stratify the train/test split to keep the rate even
on both sides).

### Features — all known BEFORE the race (no leakage)

| Feature | Type | Why |
|---|---|---|
| `grid` | numeric | Starting position — by far the strongest signal |
| `season` | numeric | The era (a driver's rookie car vs their title car) |
| `circuit_dnf_rate` | numeric | Historical attrition at the track — a leakage-free proxy for the chaos (weather, reliability) that shuffles the order |
| `driver`, `constructor`, `circuit` | one-hot | Identities |

`circuit_dnf_rate` is computed from the **training rows only**, then mapped onto the
test rows — so a race's own outcome never leaks into the feature it's scored on.

Everything is one sklearn **Pipeline** (one-hot encode the categories → pass the
numerics through → `RandomForestClassifier`). The API passes raw values; the
pipeline encodes internally, so there's no train/serve skew.

### Evaluation (held-out 20%)

| Metric | Value | Meaning |
|---|---|---|
| **ROC-AUC** | **~0.93** | How well it *ranks* drivers by podium chance (1.0 = perfect, 0.5 = coin flip) |
| **Accuracy** | **~0.90** | Right/wrong at a 0.5 threshold (but accuracy is weak on imbalanced data) |
| **Brier** | **~0.07** | Calibration of the probabilities (lower is better) — "70%" roughly means 70% |

AUC and Brier matter more than accuracy here: with only ~15% podiums, a model that
always says "no podium" already scores ~85% accuracy, so accuracy alone is
misleading. AUC says the *ranking* is strong; Brier says the *probabilities* are
trustworthy.

---

## 5. Serving — `predictor.py` / `tasks.py` / `main.py`

- The worker **preloads** the model once at startup (`worker_process_init`) plus the
  circuit→DNF-rate lookup. Per-request load cost = 0 ms.
- `predict_one` fills `circuit_dnf_rate` from the circuit id, builds a one-row
  DataFrame, and calls `predict_proba` — returning `podium_probability` and a
  convenience `podium_likely` (proba ≥ 0.5).
- `POST /predict` (async) and `POST /predict-sync` (inline) both validate the input
  against the known ids first; unknown driver/team/circuit → 422.

---

## 6. Sanity check — does it behave sensibly?

Holding everything fixed and varying only grid behaves the way intuition says:

```
  Verstappen, Red Bull, Bahrain 2023:  pole -> 95%   ...   P15 -> 43%
  Hamilton,   Mercedes, Silverstone:   P3   -> 76%
  Sargeant,   Williams, Monza 2024:    P18  -> 0%
```

A front-running car high up the grid is very likely to podium; a backmarker isn't;
a fast car starting midfield has a real-but-not-certain chance. The probability
output degrades gracefully instead of giving a falsely precise number — which is
exactly why this framing suits a noisy sport.

---

## 7. Weather, pit stops, and the leakage rule

> **A feature is only usable if you'd know its value before the race.**

- **Grid, driver, team, circuit, season** → known pre-race → used.
- **Pit/weather/attrition *chaos*** → captured via `circuit_dnf_rate` (the historical
  tendency, known in advance), not the actual values.
- **This race's actual pit stops / tyre choices / recorded weather** → these are
  *outcomes*, known only after the race → excluded, because using them is leakage.

### Clean features worth adding next (no leakage)

| Feature | Why it helps | Source |
|---|---|---|
| Qualifying gap (ms off pole) | Finer than integer grid | Jolpica `qualifying` endpoint |
| Recent driver/team form | Captures upgrades / momentum | Rolling mean of *prior* races (shifted to avoid leakage) |
| Calibrated probabilities | Tighten the Brier score | `CalibratedClassifierCV` on top of the model |
