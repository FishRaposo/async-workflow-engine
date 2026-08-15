"""Optional local authorization and rate-limiting primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from time import monotonic
from typing import Dict, Optional


class Role(IntEnum):
    VIEWER = 1
    OPERATOR = 2
    ADMIN = 3


@dataclass
class AuthPolicy:
    api_keys: Dict[str, Role] = field(default_factory=dict)
    required: bool = False

    def authorize(
        self, api_key: Optional[str], minimum_role: Role = Role.VIEWER
    ) -> bool:
        if not self.required:
            return True
        return bool(api_key and self.api_keys.get(api_key, 0) >= minimum_role)


@dataclass
class LocalRateLimiter:
    limit: int
    window_seconds: float
    _buckets: Dict[str, tuple[float, int]] = field(default_factory=dict, init=False)

    def allow(
        self, *, api_key: Optional[str] = None, client_id: Optional[str] = None
    ) -> bool:
        bucket = api_key or client_id or "anonymous"
        now = monotonic()
        window_start, count = self._buckets.get(bucket, (now, 0))
        if now - window_start >= self.window_seconds:
            window_start, count = now, 0
        if count >= self.limit:
            return False
        self._buckets[bucket] = (window_start, count + 1)
        return True
