import functools
import hashlib
import inspect
import json
import time
import uuid
from typing import Any, Callable, Optional, TypeVar, cast

import redis

F = TypeVar("F", bound=Callable[..., Any])


class RedisManager:
    """Manages Redis client connections and caching/queue setups."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """Lazily initialize Redis client."""
        if self._client is None:
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def ping(self) -> bool:
        """Pings the Redis server to verify connectivity."""
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False

    def close(self) -> None:
        """Explicitly close the Redis client connection pool."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def connect(self, max_retries: int = 3, backoff_factor: float = 0.5) -> None:
        """Eagerly connect to Redis with retry logic."""
        import time as _time

        for attempt in range(max_retries):
            try:
                self.client.ping()
                return
            except redis.RedisError:
                if attempt == max_retries - 1:
                    raise
                _time.sleep(backoff_factor * (2**attempt))


def cache(  # noqa: C901
    redis_manager: RedisManager, expire: int = 3600, key_prefix: str = "cache"
) -> Callable[[F], F]:
    """Decorator to cache function results in Redis.

    Supports sync and async functions.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            args_str = json.dumps(args, default=str)
            kwargs_str = json.dumps(sorted(kwargs.items()), default=str)
            raw_key_data = f"{args_str}:{kwargs_str}"
            key_hash = hashlib.md5(raw_key_data.encode("utf-8")).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{key_hash}"

            try:
                cached_val = redis_manager.client.get(cache_key)
                if cached_val:
                    return json.loads(cached_val)
            except Exception:
                pass

            result = await func(*args, **kwargs)

            try:
                redis_manager.client.setex(cache_key, expire, json.dumps(result))
            except Exception:
                pass

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            args_str = json.dumps(args, default=str)
            kwargs_str = json.dumps(sorted(kwargs.items()), default=str)
            raw_key_data = f"{args_str}:{kwargs_str}"
            key_hash = hashlib.md5(raw_key_data.encode("utf-8")).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{key_hash}"

            try:
                cached_val = redis_manager.client.get(cache_key)
                if cached_val:
                    return json.loads(cached_val)
            except Exception:
                pass

            result = func(*args, **kwargs)

            try:
                redis_manager.client.setex(cache_key, expire, json.dumps(result))
            except Exception:
                pass

            return result

        if inspect.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


class RedisLock:
    """Distributed lock manager using Redis, supporting both sync and async blocks."""

    def __init__(
        self,
        redis_manager: RedisManager,
        lock_name: str,
        expire_seconds: int = 10,
        acquire_timeout: float = 5.0,
    ):
        self.redis_manager = redis_manager
        self.lock_key = f"lock:{lock_name}"
        self.expire_seconds = expire_seconds
        self.acquire_timeout = acquire_timeout
        self.lock_value = str(uuid.uuid4())
        self.acquired = False

    def __enter__(self) -> "RedisLock":
        start_time = time.perf_counter()
        while time.perf_counter() - start_time < self.acquire_timeout:
            if self.redis_manager.client.set(
                self.lock_key,
                self.lock_value,
                nx=True,
                ex=self.expire_seconds,
            ):
                self.acquired = True
                return self
            time.sleep(0.1)
        raise TimeoutError(f"Could not acquire lock: {self.lock_key}")

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.acquired:
            lua_release = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                self.redis_manager.client.eval(
                    lua_release, 1, self.lock_key, self.lock_value
                )
            except Exception:
                pass
            self.acquired = False

    async def __aenter__(self) -> "RedisLock":
        import asyncio

        start_time = time.perf_counter()
        while time.perf_counter() - start_time < self.acquire_timeout:
            if self.redis_manager.client.set(
                self.lock_key,
                self.lock_value,
                nx=True,
                ex=self.expire_seconds,
            ):
                self.acquired = True
                return self
            await asyncio.sleep(0.1)
        raise TimeoutError(f"Could not acquire lock: {self.lock_key}")

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)
