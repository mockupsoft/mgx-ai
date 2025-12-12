# -*- coding: utf-8 -*-

from freezegun import freeze_time

from mgx_agent.cache import InMemoryLRUTTLCache, make_cache_key


def test_in_memory_lru_eviction_respects_recent_use():
    cache = InMemoryLRUTTLCache(max_entries=2, ttl_seconds=3600)

    cache.set("a", "A")
    cache.set("b", "B")

    # Mark "a" as most recently used.
    assert cache.get("a") == "A"

    cache.set("c", "C")

    assert cache.get("b") is None
    assert cache.get("a") == "A"
    assert cache.get("c") == "C"


def test_in_memory_ttl_expiration_removes_entries():
    with freeze_time("2025-01-01 00:00:00") as frozen:
        cache = InMemoryLRUTTLCache(max_entries=10, ttl_seconds=10)
        cache.set("k", "v")
        assert cache.get("k") == "v"

        frozen.tick(11)

        assert cache.get("k") is None
        stats = cache.stats()
        assert stats.expirations >= 1


def test_make_cache_key_is_deterministic_for_payload_order():
    payload_a = {"task": "x", "plan": "y"}
    payload_b = {"plan": "y", "task": "x"}

    key1 = make_cache_key(role="Engineer", action="WriteCode", payload=payload_a)
    key2 = make_cache_key(role="Engineer", action="WriteCode", payload=payload_b)

    assert key1 == key2
