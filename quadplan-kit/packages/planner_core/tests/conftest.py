"""Prints the verifier benchmark timings in pytest's summary, so `make check` shows them."""

from typing import Any

from core_support import BENCHMARK


def pytest_terminal_summary(terminalreporter: Any) -> None:
    for name, (median, best) in BENCHMARK.items():
        terminalreporter.write_line(
            f"benchmark: {name}: median {median:.1f} ms, best {best:.1f} ms (budget 300 ms)"
        )
