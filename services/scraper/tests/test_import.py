from scraper.main import HEALTH_FILE


def test_health_file_location() -> None:
    assert str(HEALTH_FILE) == "/tmp/scraper-healthy"
