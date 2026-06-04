"""Train the F1 podium-probability model -> model.pkl + metadata.json.

Predicts the probability a driver finishes on the podium (top 3), from features
known before the race: grid, season, circuit_dnf_rate (historical attrition at the
circuit), and driver/constructor/circuit (one-hot). No post-race info, so no
leakage. See MODEL.md.
"""

import json
import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATA_PATH = os.environ.get("DATA_PATH", "data/f1_results.csv")
MODEL_PATH = os.environ.get("MODEL_PATH", "model/model.pkl")
META_PATH = os.path.join(os.path.dirname(MODEL_PATH), "metadata.json")

CATEGORICAL = ["driver", "constructor", "circuit"]
NUMERIC = ["grid", "season", "circuit_dnf_rate"]


def is_finisher(status: str) -> bool:
    # Running at the end = Finished, "+N Laps", or Lapped. Anything else is a DNF.
    return status == "Finished" or status.startswith("+") or status == "Lapped"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    df = df.dropna(subset=["position", "grid", "season", "circuit", "status"])
    df["position"] = df["position"].astype(int)
    df["grid"] = df["grid"].astype(int)
    df["season"] = df["season"].astype(int)
    df.loc[df["grid"] == 0, "grid"] = 20  # pit-lane start -> back of grid
    df["is_dnf"] = (~df["status"].map(is_finisher)).astype(int)
    df["podium"] = (df["position"] <= 3).astype(int)  # the target: top-3 finish
    return df


def circuit_dnf_lookup(df: pd.DataFrame) -> tuple[dict, float]:
    rates = df.groupby("circuit")["is_dnf"].mean().to_dict()
    return {c: float(r) for c, r in rates.items()}, float(df["is_dnf"].mean())


def add_dnf_feature(df: pd.DataFrame, lookup: dict, fallback: float) -> pd.DataFrame:
    df = df.copy()
    df["circuit_dnf_rate"] = df["circuit"].map(lookup).fillna(fallback)
    return df


def build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)],
        remainder="passthrough",  # numerics pass through
    )
    return Pipeline([
        ("prep", preprocessor),
        ("rf", RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)),
    ])


def main() -> None:
    df = load_data()

    # Time-based split: train on past seasons, evaluate on the most recent one.
    # This mirrors the real use case (predict an upcoming race) and is fully
    # leakage-proof — the model never sees anything from the test season.
    test_season = int(df["season"].max())
    train_df = df[df["season"] < test_season].copy()
    test_df = df[df["season"] == test_season].copy()

    # Build circuit_dnf_rate from the training seasons only.
    lookup, fallback = circuit_dnf_lookup(train_df)
    train_df = add_dnf_feature(train_df, lookup, fallback)
    test_df = add_dnf_feature(test_df, lookup, fallback)

    cols = NUMERIC + CATEGORICAL
    model = build_pipeline()
    model.fit(train_df[cols], train_df["podium"])

    proba = model.predict_proba(test_df[cols])[:, 1]
    preds = (proba >= 0.5).astype(int)
    auc = roc_auc_score(test_df["podium"], proba)          # ranking quality
    acc = accuracy_score(test_df["podium"], preds)         # at a 0.5 threshold
    brier = brier_score_loss(test_df["podium"], proba)     # calibration (lower better)
    print(f"Test (season {test_season}) ROC-AUC: {auc:.3f}  |  accuracy: {acc:.3f}  |  Brier: {brier:.3f}")

    # Ship a model trained on all the data, with the lookup recomputed on all of it.
    lookup_all, fallback_all = circuit_dnf_lookup(df)
    full_df = add_dnf_feature(df, lookup_all, fallback_all)
    model.fit(full_df[cols], full_df["podium"])

    artifact = {"model": model, "circuit_dnf_rate": lookup_all, "global_dnf_rate": fallback_all}
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)

    metadata = {
        "metrics": {"roc_auc": round(float(auc), 3), "accuracy": round(float(acc), 3),
                    "brier": round(float(brier), 3)},
        "n_rows": int(len(df)),
        "podium_rate": round(float(df["podium"].mean()), 3),  # baseline rate of a podium
        "seasons": sorted(df["season"].unique().tolist()),
        "features": cols,
        "options": {c: sorted(df[c].unique().tolist()) for c in CATEGORICAL},
    }
    with open(META_PATH, "w") as f:
        json.dump(metadata, f)

    print(f"Saved {MODEL_PATH} and {META_PATH}")


if __name__ == "__main__":
    main()
