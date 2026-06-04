"""Read real race entries from the results CSV, so the API can offer a "pick a real
race" view (real drivers, teams, and grid slots) instead of free-form what-if inputs
that let you build combinations — like a driver on a team they never drove for — that
never happened."""

import os

import pandas as pd

DATA_PATH = os.environ.get("DATA_PATH", "data/f1_results.csv")

_df = None


def _load() -> pd.DataFrame:
    global _df
    if _df is None:
        df = pd.read_csv(DATA_PATH)
        df = df.dropna(subset=["season", "round", "circuit", "driver",
                               "constructor", "grid", "position"])
        for col in ["season", "round", "grid", "position"]:
            df[col] = df[col].astype(int)
        _df = df
    return _df


def list_races() -> list[dict]:
    """Every real race (season, round, circuit), newest first — for a race picker."""
    races = _load()[["season", "round", "circuit"]].drop_duplicates()
    races = races.sort_values(["season", "round"], ascending=[False, True])
    return races.to_dict("records")


def get_race(season: int, rnd: int) -> list[dict]:
    """The actual field for one race: each driver, their team, grid, and result."""
    df = _load()
    race = df[(df["season"] == season) & (df["round"] == rnd)]
    return race[["driver", "constructor", "grid", "position", "circuit"]].to_dict("records")
