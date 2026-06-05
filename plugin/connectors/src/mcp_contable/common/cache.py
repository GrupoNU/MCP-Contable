"""Simple in-memory TTL cache, to avoid hitting upstream sources repeatedly.

This is an *optional* convenience for connectors: nothing forces its use. A connector
may wrap an expensive fetch with :meth:`TTLCache.get` / :meth:`TTLCache.set` (or the
:func:`cached_call` helper) to serve repeated identical lookups from memory until the
entry expires.

CONCURRENCY
===========
The cache is NOT designed to be async-safe / thread-safe, and deliberately so: the MCP
servers run over stdio as a single-process, single-event-loop application, so there is
no concurrent mutation to guard against. ``asyncio`` coroutines never preempt each
other mid-statement, so the dict operations here are effectively atomic in that model.
If this code were ever reused in a multi-threaded context, the mutating operations
would need locking.

ZERO-RETENTION NOTE
===================
Cache contents live only in process memory and are never persisted to disk. They are
discarded when the process exits. Cache keys are caller-supplied; callers are
responsible for not embedding secrets in keys they consider sensitive.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Hashable, Optional, TypeVar

T = TypeVar("T")

# Sentinel distinguishing "key absent / expired" from a legitimately cached ``None``.
_MISSING = object()


@dataclass
class _Entry:
    """A single cache entry: the value plus its absolute expiry timestamp."""

    value: Any
    expires_at: float  # monotonic-clock seconds; compared against time.monotonic()


class TTLCache:
    """In-memory cache with per-entry time-to-live.

    Parameters
    ----------
    default_ttl:
        Default TTL in seconds applied when :meth:`set` is called without an explicit
        ``ttl``. Defaults to 300s (5 minutes).
    """

    def __init__(self, default_ttl: float = 300.0) -> None:
        self._store: dict[Hashable, _Entry] = {}
        self._default_ttl = default_ttl

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the cached value for ``key``, or ``default`` if missing/expired.

        Expired entries are evicted lazily on access.
        """
        entry = self._store.get(key, _MISSING)
        if entry is _MISSING:
            return default
        assert isinstance(entry, _Entry)
        if time.monotonic() >= entry.expires_at:
            # Lazy eviction of the stale entry.
            self._store.pop(key, None)
            return default
        return entry.value

    def set(self, key: Hashable, value: Any, ttl: Optional[float] = None) -> None:
        """Store ``value`` under ``key`` with the given ``ttl`` (seconds).

        A non-positive ``ttl`` stores nothing (treated as "do not cache").
        """
        effective_ttl = self._default_ttl if ttl is None else ttl
        if effective_ttl <= 0:
            # Don't cache; also drop any stale entry to avoid serving old data.
            self._store.pop(key, None)
            return
        self._store[key] = _Entry(
            value=value,
            expires_at=time.monotonic() + effective_ttl,
        )

    def delete(self, key: Hashable) -> None:
        """Remove ``key`` from the cache if present (no error if absent)."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Drop all entries."""
        self._store.clear()

    def __contains__(self, key: Hashable) -> bool:
        """Return True if ``key`` is present and not expired."""
        return self.get(key, _MISSING) is not _MISSING


async def cached_call(
    cache: TTLCache,
    key: Hashable,
    producer: Callable[[], Awaitable[T]],
    ttl: Optional[float] = None,
) -> T:
    """Return ``cache[key]`` if fresh, otherwise ``await producer()`` and cache it.

    Convenience wrapper for the common "read-through" pattern::

        result = await cached_call(
            cache, ("ckan", "package", pkg_id), lambda: fetch_package(pkg_id)
        )

    Parameters
    ----------
    cache:
        The :class:`TTLCache` to use.
    key:
        Cache key (must be hashable).
    producer:
        Zero-arg async callable that computes the value on a miss.
    ttl:
        TTL override for the stored value (defaults to the cache's ``default_ttl``).

    Returns
    -------
    T
        The cached or freshly produced value.
    """
    cached = cache.get(key, _MISSING)
    if cached is not _MISSING:
        return cached  # type: ignore[return-value]
    value = await producer()
    cache.set(key, value, ttl=ttl)
    return value
