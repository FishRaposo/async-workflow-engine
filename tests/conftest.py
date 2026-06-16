import pytest
from shared_core.testing import MockDatabase, MockRedisClient


@pytest.fixture
def mock_db():
    """In-memory SQLite database with the workflow schema (via shared_core)."""
    db = MockDatabase()
    yield db


@pytest.fixture
def mock_redis():
    return MockRedisClient()


# Sample workflow definitions reused across tests --------------------------- #
LINEAR_YAML = """\
name: linear
steps:
  - id: step1
    task: parse_text
  - id: step2
    task: classify_with_llm
    depends_on: [step1]
"""

BRANCHING_YAML = """\
name: branching
steps:
  - id: classify
    task: classify_with_llm
    params:
      labels: [business, spam]
      text: "business inquiry from ACME"
  - id: notify_business
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: business
  - id: notify_spam
    task: send_notification
    depends_on: [classify]
    condition:
      step: classify
      contains: spam
"""

DLQ_YAML = """\
name: dlq
steps:
  - id: ok
    task: parse_text
  - id: bad
    task: always_fail
    depends_on: [ok]
    retries: 1
"""


@pytest.fixture
def linear_yaml():
    return LINEAR_YAML


@pytest.fixture
def branching_yaml():
    return BRANCHING_YAML


@pytest.fixture
def dlq_yaml():
    return DLQ_YAML
