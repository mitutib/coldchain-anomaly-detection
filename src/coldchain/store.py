from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import redis

Step = Callable[[dict | None], tuple[dict, Any]]


class MemoryStore:
    def __init__(self) -> None:
        self.states: dict[str, dict] = {}

    def update(self, sensor: str, step: Step) -> Any:
        self.states[sensor], result = step(self.states.get(sensor))
        return result

    def ping(self) -> bool:
        return True


class RedisStore:
    def __init__(self, client: redis.Redis, ttl_seconds: int = 86400) -> None:
        self.client = client
        self.ttl = ttl_seconds

    def update(self, sensor: str, step: Step) -> Any:
        key = f"coldchain:sensor:{sensor}"
        with self.client.pipeline() as pipe:
            while True:
                try:
                    # retry if another replica wrote this sensor between our read and our write
                    pipe.watch(key)
                    raw = pipe.get(key)
                    state, result = step(json.loads(raw) if raw else None)
                    pipe.multi()
                    pipe.set(key, json.dumps(state), ex=self.ttl)
                    pipe.execute()
                    return result
                except redis.WatchError:
                    continue

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False
