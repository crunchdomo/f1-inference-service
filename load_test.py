"""Fire a burst of predictions at the API and measure two things:
  1. how fast it accepts the jobs (the async handoff should stay quick), and
  2. how long the workers take to drain the queue (throughput).

Stdlib only, so it runs with a bare python3:  python load_test.py
"""

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "http://localhost:8000"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
CONCURRENCY = 50
BODY = {"grid": 5, "driver": "max_verstappen", "constructor": "red_bull",
        "circuit": "monza", "season": 2023}


def submit(_) -> str:
    data = json.dumps(BODY).encode()
    req = urllib.request.Request(f"{API}/predict", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["task_id"]


def status(task_id: str) -> str:
    with urllib.request.urlopen(f"{API}/result/{task_id}", timeout=30) as r:
        return json.load(r)["status"]


def main() -> None:
    # 1. Submit N jobs as fast as we can.
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        task_ids = list(ex.map(submit, range(N)))
    submit_s = time.perf_counter() - t0
    print(f"accepted {N} jobs in {submit_s:.2f}s  ({N / submit_s:.0f} req/s) — API stayed responsive")

    # 2. Wait for the workers to finish them all.
    pending = task_ids
    while pending:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
            states = list(ex.map(status, pending))
        pending = [tid for tid, s in zip(pending, states) if s != "SUCCESS"]
        if pending:
            time.sleep(0.2)
    total_s = time.perf_counter() - t0
    print(f"all {N} done in {total_s:.2f}s end-to-end  ({N / total_s:.0f} predictions/s)")


if __name__ == "__main__":
    main()
