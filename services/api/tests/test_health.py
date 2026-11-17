import pytest
from api import health
from api.cli import main as cli_main
from api.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "check_db", lambda: True)
    monkeypatch.setattr(health, "check_redis", lambda: True)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": True, "redis": True}


def test_health_degraded_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "check_db", lambda: False)
    monkeypatch.setattr(health, "check_redis", lambda: True)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"


def test_version(client: TestClient) -> None:
    body = client.get("/version").json()
    assert body["version"] == "0.1.0"
    assert body["core_version"].startswith("planner_core-")


def test_cli_usage_error() -> None:
    assert cli_main([]) == 2
