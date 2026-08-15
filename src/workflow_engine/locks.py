"""Lock providers with no Redis requirement on the default path."""

from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator, Protocol


class LockProvider(Protocol):
    def acquire(self, key: str, *, ttl_seconds: int = 60) -> Iterator[bool]: ...


class InMemoryLockProvider:
    def __init__(self) -> None:
        self._keys: set[str] = set()
        self._lock = Lock()

    @contextmanager
    def acquire(self, key: str, *, ttl_seconds: int = 60) -> Iterator[bool]:
        del ttl_seconds
        with self._lock:
            acquired = key not in self._keys
            if acquired:
                self._keys.add(key)
        try:
            yield acquired
        finally:
            if acquired:
                with self._lock:
                    self._keys.discard(key)


class RedisLockProvider:
    """Thin adapter for a caller-provided Redis-compatible client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    @contextmanager
    def acquire(self, key: str, *, ttl_seconds: int = 60) -> Iterator[bool]:
        acquired = bool(self.client.set(key, "1", nx=True, ex=ttl_seconds))
        try:
            yield acquired
        finally:
            if acquired:
                self.client.delete(key)
