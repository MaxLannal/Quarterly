"""Run both load scenarios and check the prompt-12 targets. Exit code 1 if a target is missed.

    LOAD_HOST=http://localhost:8000 LOAD_LOGIN=<username> LOAD_PASSWORD=<password> \
        uv run python loadtest/run.py

Targets: POST /verify at 50 requests/second with p95 under 500 ms; forum page reads at 100
requests/second (p95 under 500 ms too); no failed requests.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
DURATION = os.environ.get("LOAD_DURATION", "60s")
SCENARIOS = [
    # (user class, users = requests/second, endpoint names checked)
    ("Verifier", 50, ["POST /verify"]),
    ("ForumReader", 100, ["GET /forum/pages/{id}", "GET /forum/pages/{id}/posts"]),
]
P95_MS = 500.0


def run(user: str, users: int, out: Path) -> list[dict[str, str]]:
    host = os.environ.get("LOAD_HOST", "http://localhost:8000")
    cmd = [
        "uvx", "--with", "httpx", "locust==2.32.4",
        "-f", str(HERE / "locustfile.py"), user,
        "--headless", "-u", str(users), "-r", str(users), "-t", DURATION,
        "--host", host, "--csv", str(out / user), "--only-summary",
    ]  # fmt: skip
    subprocess.run(cmd, check=False, env=os.environ.copy())
    with open(out / f"{user}_stats.csv", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        for user, rate, names in SCENARIOS:
            rows = {r["Name"]: r for r in run(user, rate, Path(tmp))}
            agg = rows["Aggregated"]
            rps = float(agg["Requests/s"])
            fails = int(agg["Failure Count"])
            print(f"\n{user}: {rps:.1f} requests/second, {fails} failures (target {rate}/s)")
            for name in names:
                row = rows[name]
                p95 = float(row["95%"])
                print(f"  {name}: n={row['Request Count']} median={row['Median Response Time']} ms p95={p95:.0f} ms")
                failed |= p95 >= P95_MS
            failed |= fails > 0 or rps < rate * 0.95
    print("\nRESULT:", "targets missed" if failed else "all targets met")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
