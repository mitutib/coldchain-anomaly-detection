from __future__ import annotations

import os

import redis
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest
from pydantic import BaseModel, Field

from coldchain.detectors import DefrostAwareDetector
from coldchain.store import MemoryStore, RedisStore


class Reading(BaseModel):
    sensor: str = Field(min_length=1, max_length=64)
    setpoint: float = Field(ge=-60, le=30)
    temperature: float = Field(ge=-80, le=80)


class Verdict(BaseModel):
    sensor: str
    alarm: bool


def create_app(offset: float = 1.0, n: int = 2, store=None) -> FastAPI:
    app = FastAPI(title="coldchain")
    store = store or MemoryStore()
    registry = CollectorRegistry()
    readings = Counter("coldchain_readings", "Readings received", registry=registry)
    alarms = Counter("coldchain_alarms", "Readings that raised an alarm", registry=registry)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(response: Response) -> dict:
        ok = store.ping()
        response.status_code = 200 if ok else 503
        return {"ready": ok}

    @app.post("/readings")
    def add_reading(reading: Reading) -> Verdict:
        def step(state: dict | None) -> tuple[dict, bool]:
            detector = DefrostAwareDetector(reading.setpoint + offset, n)
            if state:
                detector.restore(state)
            alarm = detector.update(reading.temperature)
            return detector.state(), alarm

        alarm = store.update(reading.sensor, step)
        readings.inc()
        if alarm:
            alarms.inc()
        return Verdict(sensor=reading.sensor, alarm=alarm)

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


def store_from_env():
    url = os.environ.get("COLDCHAIN_REDIS_URL")
    return RedisStore(redis.Redis.from_url(url, socket_timeout=2)) if url else MemoryStore()


app = create_app(
    offset=float(os.environ.get("COLDCHAIN_OFFSET", "1.0")),
    n=int(os.environ.get("COLDCHAIN_N", "2")),
    store=store_from_env(),
)
