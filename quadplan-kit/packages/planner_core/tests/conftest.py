"""Prints the verifier benchmark timings in pytest's summary, so `make check` shows them."""

from typing import Any

from core_support import BENCHMARK


def pytest_terminal_summary(terminalreporter: Any) -> None:
    for name, ms in BENCHMARK.items():
        terminalreporter.write_line(f"benchmark: {name}: {ms:.1f} ms (budget 300 ms)")
