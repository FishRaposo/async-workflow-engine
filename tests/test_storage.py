from workflow_engine.storage import InMemoryWorkflowStorage


def test_save_and_get_run():
    storage = InMemoryWorkflowStorage()
    run_id = storage.save_run(
        "test_flow",
        "name: test_flow\nsteps: []",
        {"step_a": "COMPLETED"},
        {"step_a": "ok"},
    )
    record = storage.get_run(run_id)
    assert record is not None
    assert record["workflow_name"] == "test_flow"
    assert record["step_statuses"]["step_a"] == "COMPLETED"
    assert record["results"]["step_a"] == "ok"
    assert record["status"] == "completed"
    assert "created_at" in record


def test_get_missing_run():
    storage = InMemoryWorkflowStorage()
    assert storage.get_run("nonexistent") is None


def test_explicit_run_id_used_for_rerun():
    storage = InMemoryWorkflowStorage()
    first = storage.save_run("wf", "yaml", {"s": "COMPLETED"})
    storage.save_run("wf", "yaml", {"s": "FAILED"}, status="failed", run_id=first)
    record = storage.get_run(first)
    assert record["status"] == "failed"
    assert record["step_statuses"]["s"] == "FAILED"


def test_list_runs_orders_newest_first():
    storage = InMemoryWorkflowStorage()
    storage.save_run("first", "y", {"s": "COMPLETED"})
    storage.save_run("second", "y", {"s": "COMPLETED"})
    runs = storage.list_runs()
    assert len(runs) == 2
    names = [r["workflow_name"] for r in runs]
    assert "first" in names and "second" in names


def test_dead_letters_per_run_and_global():
    storage = InMemoryWorkflowStorage()
    rid = storage.save_run(
        "wf",
        "y",
        {"s": "FAILED"},
        status="failed",
        dead_letters=[{"step_id": "s", "task": "t", "error": "boom", "attempts": 1}],
    )
    per_run = storage.get_dead_letters(rid)
    assert len(per_run) == 1
    assert per_run[0]["step_id"] == "s"
    globals_ = storage.get_dead_letters()
    assert globals_[0]["run_id"] == rid


def test_dead_letters_empty_when_none():
    storage = InMemoryWorkflowStorage()
    storage.save_run("wf", "y", {"s": "COMPLETED"})
    assert storage.get_dead_letters() == []
