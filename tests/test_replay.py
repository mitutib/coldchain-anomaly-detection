from coldchain.generate import SENSORS, generate
from coldchain.replay import replay


def test_replay_sends_every_reading_in_order_with_its_setpoint():
    readings = generate(days=1)
    sent = []

    def send(body):
        sent.append(body)
        return {"alarm": body["temperature"] > 100}

    summary = replay(readings, send)
    assert len(sent) == len(readings) == summary["readings"]
    assert sent[0] == {
        "sensor": readings[0].sensor,
        "setpoint": SENSORS[readings[0].sensor][1],
        "temperature": readings[0].temperature,
    }
    assert summary["alarms"] == 0


def test_replay_counts_alarms():
    readings = generate(days=1)
    summary = replay(readings, lambda body: {"alarm": body["sensor"] == "meat"})
    assert summary["alarms"] == sum(r.sensor == "meat" for r in readings)
