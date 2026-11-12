"""The Redis operations the auth code needs, behind one small typed wrapper."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import redis
from fastapi import Request

from api.config import get_settings


class Store:
    def __init__(self, client: Any) -> None:
        self._r = client

    def get(self, key: str) -> str | None:
        value = self._r.get(key)
        return None if value is None else str(value)

    def put(self, key: str, value: str, ttl: int) -> None:
        self._r.set(key, value, ex=ttl)

    def getdel(self, key: str) -> str | None:
        value = self._r.getdel(key)
        return None if value is None else str(value)

    def delete(self, *keys: str) -> None:
        if keys:
            self._r.delete(*keys)

    def ttl(self, key: str) -> int:
        return int(self._r.ttl(key))

    def incr(self, key: str, ttl: int) -> int:
        """Count one event in a fixed window that starts at the first event and lasts `ttl`."""
        pipe = self._r.pipeline()
        pipe.set(key, 0, ex=ttl, nx=True)
        pipe.incr(key)
        return int(pipe.execute()[1])

    def count(self, key: str) -> int:
        return int(self._r.get(key) or 0)

    def sadd(self, key: str, member: str, ttl: int) -> None:
        pipe = self._r.pipeline()
        pipe.sadd(key, member)
        pipe.expire(key, ttl)
        pipe.execute()

    def srem(self, key: str, member: str) -> None:
        self._r.srem(key, member)

    def smembers(self, key: str) -> set[str]:
        return {str(m) for m in self._r.smembers(key)}


@lru_cache
def _client(url: str) -> Any:
    return redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)


def get_store(request: Request) -> Store:
    """FastAPI dependency. Tests put a fakeredis client on `app.state.redis`."""
    client = getattr(request.app.state, "redis", None)
    return Store(client if client is not None else _client(get_settings().redis_url))
