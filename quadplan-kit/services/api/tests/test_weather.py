"""The homepage scene's weather: fetched by the server, cached, never from the visitor's browser.
Open-Meteo is replaced by a fake; tests never call the internet."""

import pytest
from api.main import app
from api.routers import weather
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    weather._cache.reset()


def test_weather_is_fetched_once_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake() -> weather.WeatherOut:
        calls.append(1)
        return weather.WeatherOut(weather_code=61, cloud_cover=90)

    monkeypatch.setattr(weather, "fetch_open_meteo", fake)
    client = TestClient(app)
    for _ in range(3):
        r = client.get("/weather")
        assert r.status_code == 200
        assert r.json() == {"weather_code": 61, "cloud_cover": 90}
    assert len(calls) == 1
    assert "max-age" in r.headers["cache-control"]


def test_weather_refreshes_after_15_minutes(monkeypatch: pytest.MonkeyPatch) -> None:
    codes = iter([0, 71])
    monkeypatch.setattr(
        weather,
        "fetch_open_meteo",
        lambda: weather.WeatherOut(weather_code=next(codes), cloud_cover=0),
    )
    assert weather.current_weather(now=1000.0) == weather.WeatherOut(weather_code=0, cloud_cover=0)
    assert weather.current_weather(now=1000.0 + 14 * 60) == weather.WeatherOut(
        weather_code=0, cloud_cover=0
    )
    assert weather.current_weather(now=1000.0 + 16 * 60) == weather.WeatherOut(
        weather_code=71, cloud_cover=0
    )


def test_weather_unavailable_is_503_and_not_retried_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def down() -> weather.WeatherOut:
        calls.append(1)
        raise OSError("offline")

    monkeypatch.setattr(weather, "fetch_open_meteo", down)
    client = TestClient(app)
    assert client.get("/weather").status_code == 503
    assert client.get("/weather").status_code == 503
    assert len(calls) == 1


def test_a_failure_keeps_the_last_good_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        weather, "fetch_open_meteo", lambda: weather.WeatherOut(weather_code=3, cloud_cover=80)
    )
    weather.current_weather(now=0.0)

    def down() -> weather.WeatherOut:
        raise OSError("offline")

    monkeypatch.setattr(weather, "fetch_open_meteo", down)
    assert weather.current_weather(now=20 * 60.0) == weather.WeatherOut(
        weather_code=3, cloud_cover=80
    )
