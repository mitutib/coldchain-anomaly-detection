import threading
import time

import fakeredis
import pytest
import redis

from coldchain.store import MemoryStore, RedisStore, StoreUnavailable


@pytest.fixture(params=["memory", "redis"])
def store(request):
    if request.param == "memory":
        return MemoryStore()
    return RedisStore(fakeredis.FakeRedis())


def count(state):
    seen = (state or {"seen": 0})["seen"] + 1
    return {"seen": seen}, seen


def test_first_update_starts_from_nothing(store):
    assert store.update("dairy", count) == 1


def test_state_is_kept_between_updates(store):
    store.update("dairy", count)
    assert store.update("dairy", count) == 2


def test_sensors_are_independent(store):
    store.update("dairy", count)
    assert store.update("meat", count) == 1


def test_two_redis_stores_share_state():
    server = fakeredis.FakeServer()
    first = RedisStore(fakeredis.FakeRedis(server=server))
    second = RedisStore(fakeredis.FakeRedis(server=server))
    first.update("dairy", count)
    assert second.update("dairy", count) == 2


def test_ping(store):
    assert store.ping() is True


def test_unreachable_redis_raises_store_unavailable():
    store = RedisStore(redis.Redis(port=1, socket_connect_timeout=0.2))
    with pytest.raises(StoreUnavailable):
        store.update("dairy", count)


def test_write_between_read_and_write_is_retried_without_losing_it():
    server = fakeredis.FakeServer()
    store = RedisStore(fakeredis.FakeRedis(server=server))
    rival = RedisStore(fakeredis.FakeRedis(server=server))
    states = []

    def step(state):
        states.append(state)
        if len(states) == 1:
            # written from inside step so it lands after our read and before our write
            rival.update("dairy", count)
        return count(state)

    assert store.update("dairy", step) == 2
    assert states == [None, {"seen": 1}]
    assert rival.update("dairy", count) == 3


def test_parallel_updates_of_one_sensor_are_all_counted():
    threads, updates = 8, 25
    server = fakeredis.FakeServer()
    start = threading.Barrier(threads)
    results, errors = [], []

    def slow_count(state):
        time.sleep(0)  # hand over to another thread between the read and the write
        return count(state)

    def work():
        store = RedisStore(fakeredis.FakeRedis(server=server))
        try:
            start.wait()
            for _ in range(updates):
                results.append(store.update("dairy", slow_count))
        except Exception as error:
            errors.append(error)

    workers = [threading.Thread(target=work, daemon=True) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert not errors
    assert not any(worker.is_alive() for worker in workers)
    assert sorted(results) == list(range(1, threads * updates + 1))
    assert RedisStore(fakeredis.FakeRedis(server=server)).update("dairy", count) == threads * updates + 1
