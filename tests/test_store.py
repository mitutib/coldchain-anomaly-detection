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
