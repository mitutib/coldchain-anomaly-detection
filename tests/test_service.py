import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

from coldchain.service import create_app
from coldchain.store import RedisStore


@pytest.fixture
def client():
    return TestClient(create_app(offset=1.0, n=2))


def send(client, temperature, sensor="dairy", setpoint=4.0):
    body = {"sensor": sensor, "setpoint": setpoint, "temperature": temperature}
    return client.post("/readings", json=body)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_normal_reading_does_not_alarm(client):
    response = send(client, 4.2)
    assert response.status_code == 200
    assert response.json() == {"sensor": "dairy", "alarm": False}


def test_slow_drift_alarms_on_the_second_high_reading(client):
    # threshold is 4.0 + 1.0, so 5.2 is the first reading above it and 5.8 the second
    alarms = [send(client, t).json()["alarm"] for t in (4.0, 4.6, 5.2, 5.8)]
    assert alarms == [False, False, False, True]


def test_defrost_spike_does_not_alarm(client):
    alarms = [send(client, t).json()["alarm"] for t in (4.0, 8.0, 8.0, 8.0, 8.0, 4.0)]
    assert not any(alarms)


def test_sensors_do_not_share_state(client):
    send(client, 5.5, sensor="dairy")
    assert send(client, 5.5, sensor="deli").json()["alarm"] is False


def test_invalid_reading_is_rejected(client):
    assert send(client, 500.0).status_code == 422
    assert client.post("/readings", json={"sensor": "dairy"}).status_code == 422


def test_metrics_count_readings_and_alarms(client):
    for t in (4.0, 5.5, 5.5):
        send(client, t)
    text = client.get("/metrics").text
    assert "coldchain_readings_total 3.0" in text
    assert "coldchain_alarms_total 1.0" in text


def test_replicas_sharing_a_store_agree():
    server = fakeredis.FakeServer()
    replicas = [
        TestClient(create_app(store=RedisStore(fakeredis.FakeRedis(server=server)))) for _ in range(2)
    ]
    alarms = [send(replicas[i % 2], t).json()["alarm"] for i, t in enumerate((4.0, 4.6, 5.2, 5.8))]
    assert alarms == [False, False, False, True]


def test_ready_reports_the_store(client):
    assert client.get("/ready").status_code == 200


def test_not_ready_when_the_store_is_down():
    class Down:
        def ping(self):
            return False

    assert TestClient(create_app(store=Down())).get("/ready").status_code == 503


def test_reading_is_refused_when_the_store_is_down():
    store = RedisStore(redis.Redis(port=1, socket_connect_timeout=0.2))
    response = send(TestClient(create_app(store=store)), 5.0)
    assert response.status_code == 503


def metric(client, name):
    for line in client.get("/metrics").text.splitlines():
        if line.split(" ")[0] == name:
            return float(line.split(" ")[1])
    raise AssertionError(f"{name} not found")


def test_metrics_record_the_offset_from_the_setpoint(client):
    for t in (4.2, 4.4, 9.0):
        send(client, t, setpoint=4.0)
    text = client.get("/metrics").text
    assert 'coldchain_reading_offset_degrees_bucket{le="1.0"} 2.0' in text
    assert 'coldchain_reading_offset_degrees_bucket{le="+Inf"} 3.0' in text


def test_metrics_time_each_request(client):
    send(client, 4.0)
    assert metric(client, "coldchain_request_seconds_count") == 1.0


def test_metrics_count_store_errors():
    store = RedisStore(redis.Redis(port=1, socket_connect_timeout=0.2))
    client = TestClient(create_app(store=store))
    send(client, 5.0)
    assert metric(client, "coldchain_store_errors_total") == 1.0
    assert metric(client, "coldchain_readings_total") == 0.0


def test_metrics_count_alarm_starts_not_alarming_readings(client):
    # two separate episodes: three alarming readings in the first, two in the second
    for t in (4.0, 5.5, 5.5, 5.5, 5.5, 4.0, 5.5, 5.5, 5.5):
        send(client, t)
    assert metric(client, "coldchain_alarms_total") == 5.0
    assert metric(client, "coldchain_alarm_starts_total") == 2.0
