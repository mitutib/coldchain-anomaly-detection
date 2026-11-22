from __future__ import annotations

import os

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, generate_latest
from pydantic import BaseModel, Field

from coldchain.detectors import DefrostAwareDetector


class Reading(BaseModel):
    sensor: str = Field(min_length=1, max_length=64)
    setpoint: float = Field(ge=-60, le=30)
    temperature: float = Field(ge=-80, le=80)


class Verdict(BaseModel):
    sensor: str
    alarm: bool


def create_app(offset: float = 1.0, n: int = 2) -> FastAPI:
    app = FastAPI(title="coldchain")
    registry = CollectorRegistry()
    readings = Counter("coldchain_readings", "Readings received", registry=registry)
    alarms = Counter("coldchain_alarms", "Readings that raised an alarm", registry=registry)
    # one detector per sensor, kept in memory: state is lost on restart and not shared between replicas
    detectors: dict[str, DefrostAwareDetector] = {}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/readings")
    def add_reading(reading: Reading) -> Verdict:
        detector = detectors.get(reading.sensor)
        if detector is None:
            detector = detectors[reading.sensor] = DefrostAwareDetector(reading.setpoint + offset, n)
        alarm = detector.update(reading.temperature)
        readings.inc()
        if alarm:
            alarms.inc()
        return Verdict(sensor=reading.sensor, alarm=alarm)

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app(
    offset=float(os.environ.get("COLDCHAIN_OFFSET", "1.0")),
    n=int(os.environ.get("COLDCHAIN_N", "2")),
)
