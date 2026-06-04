"""Fetch F1 race results (2014-2024) from the Jolpica/Ergast API into
data/f1_results.csv. Run once; the CSV is committed so the build stays offline.
Stdlib only, so it runs with a bare python3.
"""

import csv
import json
import os
import time
import urllib.request

SEASONS = range(2014, 2025)
URL = "https://api.jolpi.ca/ergast/f1/{season}/results/?limit=100&offset={offset}"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "f1_results.csv")
FIELDS = ["season", "round", "circuit", "driver", "constructor", "grid", "position", "status"]


def fetch_season(season: int) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:  # paginate; Jolpica caps results at 100 per page
        with urllib.request.urlopen(URL.format(season=season, offset=offset), timeout=30) as resp:
            data = json.load(resp)
        mrdata = data["MRData"]
        for race in mrdata["RaceTable"]["Races"]:
            circuit = race["Circuit"]["circuitId"]
            for res in race["Results"]:
                rows.append({
                    "season": season,
                    "round": race["round"],
                    "circuit": circuit,
                    "driver": res["Driver"]["driverId"],
                    "constructor": res["Constructor"]["constructorId"],
                    "grid": res["grid"],
                    "position": res["position"],
                    "status": res["status"],
                })
        offset += 100
        if offset >= int(mrdata["total"]):
            break
        time.sleep(0.3)  # be polite to a free API
    return rows


def main() -> None:
    rows = []
    for season in SEASONS:
        season_rows = fetch_season(season)
        print(f"{season}: {len(season_rows)} results")
        rows.extend(season_rows)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
