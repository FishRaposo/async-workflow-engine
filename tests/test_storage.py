from workflow_engine.storage import InMemoryWorkflowStorage


def test_save_and_get_run():
    storage = InMemoryWorkflowStorage()
    storage.save_run("run-1", "test_flow", {"step_a": "COMPLETED"}, {"step_a": "ok"})

    record = storage.get_run("run-1")
    assert record is not None
    assert record["workflow_name"] == "test_flow"
    assert record["statuses"]["step_a"] == "COMPLETED"
    assert record["results"]["step_a"] == "ok"
    assert "timestamp" in record


def test_get_missing_run():
    storage = InMemoryWorkflowStorage()
    assert storage.get_run("nonexistent") is None


def test_overwrite_run():
    storage = InMemoryWorkflowStorage()
    storage.save_run("run-1", "first", {"s": "PENDING"})
    storage.save_run("run-1", "second", {"s": "COMPLETED"})
    assert storage.get_run("run-1")["workflow_name"] == "second"
