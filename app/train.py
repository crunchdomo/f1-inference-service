"""Train the F1 finishing-position model -> model.pkl + metadata.json.

Features (all known before a race): grid, season, circuit_dnf_rate (historical
attrition at the circuit), and driver/constructor/circuit one-hot encoded. The
race's actual weather/pit/tyre data is left out on purpose — those are outcomes,
so using them would be leakage. See MODEL.md.
"""

import json
import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
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
        ("rf", RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)),
    ])


def main() -> None:
    df = load_data()

    # Split first, then build circuit_dnf_rate from the train rows only, so the
    # test score isn't contaminated by the held-out races' own outcomes.
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    lookup, fallback = circuit_dnf_lookup(train_df)
    train_df = add_dnf_feature(train_df, lookup, fallback)
    test_df = add_dnf_feature(test_df, lookup, fallback)

    cols = NUMERIC + CATEGORICAL
    model = build_pipeline()
    model.fit(train_df[cols], train_df["position"])

    preds = model.predict(test_df[cols])
    mae = mean_absolute_error(test_df["position"], preds)
    r2 = r2_score(test_df["position"], preds)
    print(f"Test MAE: {mae:.2f} positions  |  R2: {r2:.3f}  |  rows: {len(df)}")

    # Ship a model trained on all the data, with the lookup recomputed on all of it.
    lookup_all, fallback_all = circuit_dnf_lookup(df)
    full_df = add_dnf_feature(df, lookup_all, fallback_all)
    model.fit(full_df[cols], full_df["position"])

    artifact = {"model": model, "circuit_dnf_rate": lookup_all, "global_dnf_rate": fallback_all}
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)

    metadata = {
        "metrics": {"mae": round(float(mae), 2), "r2": round(float(r2), 3)},
        "n_rows": int(len(df)),
        "seasons": sorted(df["season"].unique().tolist()),
        "features": cols,
        "options": {c: sorted(df[c].unique().tolist()) for c in CATEGORICAL},
    }
    with open(META_PATH, "w") as f:
        json.dump(metadata, f)

    print(f"Saved {MODEL_PATH} and {META_PATH}")


if __name__ == "__main__":
    main()
