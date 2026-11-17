"""Container entry point: prove Chromium launches, mark healthy, then idle (no jobs yet)."""

import time
from pathlib import Path

HEALTH_FILE = Path("/tmp/scraper-healthy")


def self_test() -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        version = browser.version
        browser.close()
    return version


def main() -> None:  # pragma: no cover - runs only inside the container
    version = self_test()
    HEALTH_FILE.write_text(version)
    print(f"scraper: chromium {version} ready; no jobs configured", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":  # pragma: no cover
    main()
