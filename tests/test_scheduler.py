from datetime import datetime, timedelta, timezone

import pytest

from workflow_engine.scheduler import (
    WorkflowScheduler,
    is_valid_cron,
    next_run_time,
)

WF = "name: wf\nsteps:\n  - id: s\n    task: parse_text\n"


def test_is_valid_cron():
    assert is_valid_cron("*/15 * * * *")
    assert is_valid_cron("0 2 * * *")
    assert not is_valid_cron("not a cron")


def test_next_run_time_advances():
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    nxt = next_run_time("0 * * * *", base)  # top of every hour
    assert nxt == datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)


def test_register_sets_next_run():
    sched = WorkflowScheduler()
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    s = sched.register("nightly", "0 2 * * *", WF, now=base)
    assert s.next_run == datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)


def test_register_invalid_cron_raises():
    sched = WorkflowScheduler()
    with pytest.raises(ValueError, match="Invalid cron"):
        sched.register("bad", "nope", WF)


def test_due_returns_ready_schedules():
    sched = WorkflowScheduler()
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    sched.register("hourly", "0 * * * *", WF, now=base)
    # next_run is 01:00; nothing due at 00:30, due at 01:30
    assert sched.due(now=base + timedelta(minutes=30)) == []
    ready = sched.due(now=base + timedelta(hours=1, minutes=30))
    assert len(ready) == 1
    assert ready[0].name == "hourly"


def test_mark_ran_advances_next_run():
    sched = WorkflowScheduler()
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    sched.register("hourly", "0 * * * *", WF, now=base)
    sched.mark_ran("hourly", now=base + timedelta(hours=1, minutes=5))
    s = sched.schedules["hourly"]
    assert s.last_run is not None
    assert s.next_run == datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)


def test_unregister():
    sched = WorkflowScheduler()
    sched.register("x", "0 * * * *", WF)
    assert sched.unregister("x") is True
    assert sched.unregister("x") is False


def test_list_schedules():
    sched = WorkflowScheduler()
    sched.register("x", "0 * * * *", WF)
    listed = sched.list_schedules()
    assert listed[0]["name"] == "x"
    assert listed[0]["cron"] == "0 * * * *"
