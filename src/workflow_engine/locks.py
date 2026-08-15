"""Lock providers with no Redis requirement on the default path."""

from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator, Protocol
from uuid import uuid4

_RELEASE_IF_OWNER = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


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
    """Optional adapter over the vendored ``RedisManager`` or a compatible client."""

    def __init__(self, client: Any) -> None:
        self.client = client

    @classmethod
    def from_manager(cls, manager: Any) -> "RedisLockProvider":
        """Build an opt-in lock provider without creating a Redis connection."""
        return cls(manager.client)

    @contextmanager
    def acquire(self, key: str, *, ttl_seconds: int = 60) -> Iterator[bool]:
        owner_token = str(uuid4())
        acquired = bool(self.client.set(key, owner_token, nx=True, ex=ttl_seconds))
        try:
            yield acquired
        finally:
            if acquired:
                self.client.eval(_RELEASE_IF_OWNER, 1, key, owner_token)
