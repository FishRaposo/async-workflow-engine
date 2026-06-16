from workflow_engine.webhooks import WebhookRegistry

WF = "name: wf\nsteps:\n  - id: s\n    task: parse_text\n"


def test_register_and_get():
    reg = WebhookRegistry()
    reg.register("lead", WF, "lead intake hook")
    trigger = reg.get("lead")
    assert trigger is not None
    assert trigger.yaml_definition == WF
    assert trigger.description == "lead intake hook"


def test_get_missing_returns_none():
    reg = WebhookRegistry()
    assert reg.get("nope") is None


def test_unregister():
    reg = WebhookRegistry()
    reg.register("lead", WF)
    assert reg.unregister("lead") is True
    assert reg.unregister("lead") is False


def test_list_triggers():
    reg = WebhookRegistry()
    reg.register("a", WF, "first")
    reg.register("b", WF)
    names = {t["name"] for t in reg.list_triggers()}
    assert names == {"a", "b"}
