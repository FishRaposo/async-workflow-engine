import pytest
from shared_core.testing import MockDatabase, MockRedisClient


@pytest.fixture
def mock_db():
    db = MockDatabase()
    yield db


@pytest.fixture
def mock_redis():
    return MockRedisClient()
