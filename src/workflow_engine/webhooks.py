"""Webhook trigger registry.

Maps a webhook name to a workflow YAML definition. ``POST /webhooks/{name}``
fires the associated workflow; the request body is made available so a workflow
can react to external events. Kept deliberately small and in-memory — a
dashboard registers triggers and the API resolves them.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class WebhookTrigger:
    name: str
    yaml_definition: str
    description: str = ""


@dataclass
class WebhookRegistry:
    triggers: Dict[str, WebhookTrigger] = field(default_factory=dict)

    def register(
        self, name: str, yaml_definition: str, description: str = ""
    ) -> WebhookTrigger:
        trigger = WebhookTrigger(name, yaml_definition, description)
        self.triggers[name] = trigger
        return trigger

    def get(self, name: str) -> Optional[WebhookTrigger]:
        return self.triggers.get(name)

    def unregister(self, name: str) -> bool:
        return self.triggers.pop(name, None) is not None

    def list_triggers(self) -> List[Dict]:
        return [
            {"name": t.name, "description": t.description}
            for t in self.triggers.values()
        ]
