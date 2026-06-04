"""Tests for the in-memory TTL cache and the read-through cached_call helper."""

from __future__ import annotations

import pytest

from mcp_contable.common import TTLCache, cached_call
from mcp_contable.common import cache as cache_mod


class _FakeClock:
    """A controllable stand-in for time.monotonic() (no real sleeping)."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    """Patch the cache module's monotonic clock so TTL is fully deterministic."""
    fake = _FakeClock()
    monkeypatch.setattr(cache_mod.time, "monotonic", fake)
    return fake


def test_set_and_get_basic(clock: _FakeClock) -> None:
    """A value set under a key reads back while fresh."""
    cache = TTLCache()
    cache.set("k", 42)
    assert cache.get("k") == 42


def test_get_missing_returns_default() -> None:
    """A missing key returns the supplied default (None by default)."""
    cache = TTLCache()
    assert cache.get("nope") is None
    assert cache.get("nope", "fallback") == "fallback"


def test_cached_none_is_distinguished_from_missing(clock: _FakeClock) -> None:
    """A legitimately cached None is returned, not treated as a miss."""
    cache = TTLCache()
    cache.set("k", None)
    assert cache.get("k", "default") is None


def test_ttl_expiration(clock: _FakeClock) -> None:
    """Entries expire once the (monotonic) clock passes their TTL."""
    cache = TTLCache()
    cache.set("k", "v", ttl=10.0)
    assert cache.get("k") == "v"

    clock.advance(9.0)
    assert cache.get("k") == "v"  # still fresh

    clock.advance(1.0)  # now exactly at expiry (>= expires_at -> expired)
    assert cache.get("k") is None


def test_default_ttl_used_when_none(clock: _FakeClock) -> None:
    """default_ttl applies when set() is called without an explicit ttl."""
    cache = TTLCache(default_ttl=5.0)
    cache.set("k", "v")
    clock.advance(4.0)
    assert cache.get("k") == "v"
    clock.advance(1.0)
    assert cache.get("k") is None


def test_non_positive_ttl_does_not_cache(clock: _FakeClock) -> None:
    """A ttl <= 0 stores nothing and evicts any stale entry."""
    cache = TTLCache()
    cache.set("k", "fresh", ttl=10.0)
    cache.set("k", "ignored", ttl=0)
    assert cache.get("k") is None
    assert "k" not in cache


def test_contains_operator(clock: _FakeClock) -> None:
    """`in` reflects presence and freshness."""
    cache = TTLCache()
    cache.set("k", "v", ttl=10.0)
    assert "k" in cache
    assert "absent" not in cache
    clock.advance(10.0)
    assert "k" not in cache  # expired


def test_delete(clock: _FakeClock) -> None:
    """delete removes a key; deleting an absent key is a no-op."""
    cache = TTLCache()
    cache.set("k", "v")
    cache.delete("k")
    assert "k" not in cache
    cache.delete("k")  # no error
    cache.delete("never-existed")  # no error


def test_clear(clock: _FakeClock) -> None:
    """clear drops all entries."""
    cache = TTLCache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert "a" not in cache
    assert "b" not in cache


async def test_cached_call_calls_producer_once_within_ttl(clock: _FakeClock) -> None:
    """Read-through: the producer runs once on a miss, then results are cached."""
    cache = TTLCache()
    calls = {"n": 0}

    async def producer() -> str:
        calls["n"] += 1
        return "value"

    first = await cached_call(cache, "key", producer, ttl=100.0)
    second = await cached_call(cache, "key", producer, ttl=100.0)

    assert first == "value"
    assert second == "value"
    assert calls["n"] == 1  # producer invoked exactly once within the TTL


async def test_cached_call_reruns_after_expiry(clock: _FakeClock) -> None:
    """Once the entry expires, the producer runs again."""
    cache = TTLCache()
    calls = {"n": 0}

    async def producer() -> int:
        calls["n"] += 1
        return calls["n"]

    first = await cached_call(cache, "key", producer, ttl=10.0)
    assert first == 1
    assert calls["n"] == 1

    clock.advance(10.0)  # expire it
    second = await cached_call(cache, "key", producer, ttl=10.0)
    assert second == 2
    assert calls["n"] == 2
