import time
from typing import Any, Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from workflow_engine.internal.vendor_core.database import Base


class MockDatabase:
    """Helper to provision an in-memory SQLite database with schema for testing."""

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        """Generator providing database sessions."""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()


class MockRedisClient:
    """In-memory mock of redis.Redis client for testing purposes."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, float] = {}

    def ping(self) -> bool:
        """Mock ping command."""
        return True

    def get(self, key: str) -> Optional[str]:
        """Mock GET command with TTL evaluation."""
        if key in self.ttls and time.time() > self.ttls[key]:
            self.delete(key)
            return None
        return self.data.get(key)

    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
    ) -> bool:
        """Mock SET command with optional TTL (ex/px) and condition (nx)."""
        if nx and key in self.data:
            if key not in self.ttls or time.time() <= self.ttls[key]:
                return False

        self.data[key] = str(value)
        if ex:
            self.ttls[key] = time.time() + ex
        elif px:
            self.ttls[key] = time.time() + (px / 1000.0)
        else:
            self.ttls.pop(key, None)
        return True

    def setex(self, key: str, time_val: int, value: str) -> bool:
        """Mock SETEX command."""
        return self.set(key, value, ex=time_val)

    def delete(self, *keys: str) -> int:
        """Mock DEL command."""
        count = 0
        for key in keys:
            if key in self.data:
                self.data.pop(key, None)
                self.ttls.pop(key, None)
                count += 1
        return count

    def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        """Mock EVAL script command (simulates atomic lock releases)."""
        # Checks if script matches atomic lock release check pattern
        if 'redis.call("get", KEYS[1]) == ARGV[1]' in script:
            key = args[0]
            val = args[1]
            if self.get(key) == str(val):
                self.delete(key)
                return 1
            return 0
        return 0
