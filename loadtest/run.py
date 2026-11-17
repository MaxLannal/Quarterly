"""Run both load scenarios and check the prompt-12 targets. Exit code 1 if a target is missed.

    LOAD_HOST=http://localhost:8000 LOAD_LOGIN=<username> LOAD_PASSWORD=<password> \
        uv run python loadtest/run.py

    # in the stack's own Docker network, through nginx like real traffic:
    LOAD_DOCKER_NETWORK=quarterly_default LOAD_HOST=http://web:5173/api \
        LOAD_LOGIN=... LOAD_PASSWORD=... uv run python loadtest/run.py

Targets (prompt 12): POST /verify at 50 requests/second with p95 under 500 ms; forum page
reads at 100 requests/second. No failed requests. The forum p95 is printed for information:
the prompt sets no latency target for it.
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
#: Endpoints with a p95 target (prompt 12 gives one for /verify only).
P95_CHECKED = {"POST /verify"}
P95_MS = 500.0


def run(user: str, users: int, out: Path) -> list[dict[str, str]]:
    host = os.environ.get("LOAD_HOST", "http://localhost:8000")
    args = [
        user, "--headless", "-u", str(users), "-r", str(users), "-t", DURATION,
        "--host", host, "--only-summary",
    ]  # fmt: skip
    network = os.environ.get("LOAD_DOCKER_NETWORK")
    if network:
        # Inside the stack's network, next to the server, as a load generator would be on a
        # real deployment (Docker Desktop's port forwarding on a Mac adds ~100 ms per request
        # once there are ~100 open connections).
        cmd = [
            "docker", "run", "--rm", "--network", network,
            "-e", "LOAD_LOGIN", "-e", "LOAD_PASSWORD",
            "-v", f"{HERE.resolve()}:/mnt/lt:ro", "-v", f"{out}:/mnt/out",
            "locustio/locust:2.32.4", "-f", "/mnt/lt/locustfile.py",
            *args, "--csv", f"/mnt/out/{user}",
        ]  # fmt: skip
    else:
        cmd = [
            "uvx", "locust==2.32.4", "-f", str(HERE / "locustfile.py"),
            *args, "--csv", str(out / user),
        ]  # fmt: skip
    subprocess.run(cmd, check=False, env=os.environ.copy())
    with open(out / f"{user}_stats.csv", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        os.chmod(tmp, 0o777)  # the locust container writes its CSV files here
        for user, rate, names in SCENARIOS:
            rows = {r["Name"]: r for r in run(user, rate, Path(tmp))}
            agg = rows["Aggregated"]
            rps = float(agg["Requests/s"])
            fails = int(agg["Failure Count"])
            print(f"\n{user}: {rps:.1f} requests/second, {fails} failures (target {rate}/s)")
            for name in names:
                row = rows[name]
                p95 = float(row["95%"])
                median = row["Median Response Time"]
                print(f"  {name}: n={row['Request Count']} median={median} ms p95={p95:.0f} ms")
                failed |= name in P95_CHECKED and p95 >= P95_MS
            failed |= fails > 0 or rps < rate * 0.95
    print("\nRESULT:", "targets missed" if failed else "all targets met")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
