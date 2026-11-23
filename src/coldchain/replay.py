"""Send generated readings to a running service, in time order.

Usage: python -m coldchain.replay [--url http://localhost:8000] [--days 7] [--noise-scale 1.0]
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from collections.abc import Callable

from coldchain.generate import SENSORS, Reading, generate


def replay(readings: list[Reading], send: Callable[[dict], dict]) -> dict:
    alarms = 0
    for r in readings:
        verdict = send({"sensor": r.sensor, "setpoint": SENSORS[r.sensor][1], "temperature": r.temperature})
        alarms += bool(verdict["alarm"])
    return {"readings": len(readings), "alarms": alarms}


def http_sender(url: str, prefix: str = "") -> Callable[[dict], dict]:
    def send(body: dict) -> dict:
        body = {**body, "sensor": prefix + body["sensor"]}
        request = urllib.request.Request(
            f"{url}/readings", data=json.dumps(body).encode(), headers={"content-type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    return send


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--noise-scale", type=float, default=1.0)
    p.add_argument("--prefix", default="", help="prepended to sensor names, to keep runs apart")
    a = p.parse_args()
    readings = generate(a.days, a.seed, a.noise_scale)
    print(replay(readings, http_sender(a.url, a.prefix)))


if __name__ == "__main__":
    main()
