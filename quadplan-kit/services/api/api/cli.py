"""Command-line entry points used by the Makefile (`make seed`, `make golden`)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def golden() -> int:
    plans = sorted((REPO_ROOT / "data" / "golden").rglob("*.yaml"))
    if not plans:
        print("golden: no golden plans yet")
        return 0
    print(f"golden: {len(plans)} plan files found but no runner yet")
    return 0


def seed() -> int:
    print("seed: no seed loader yet")
    return 0


def main(argv: list[str]) -> int:
    commands = {"golden": golden, "seed": seed}
    if len(argv) != 1 or argv[0] not in commands:
        print(f"usage: python -m api.cli {{{'|'.join(commands)}}}", file=sys.stderr)
        return 2
    return commands[argv[0]]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
