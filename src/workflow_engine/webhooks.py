"""Webhook trigger registry.

Maps a webhook name to a workflow YAML definition. ``POST /webhooks/{name}``
fires the associated workflow; the request body is made available so a workflow
can react to external events. Kept deliberately small and in-memory — a
dashboard registers triggers and the API resolves them.
"""

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .contracts import WebhookStore


@dataclass
class WebhookTrigger:
    name: str
    yaml_definition: str
    description: str = ""
    secret: Optional[str] = None


@dataclass
class InMemoryWebhookStore:
    """Process-local webhook persistence adapter."""

    records: Dict[str, WebhookTrigger] = field(default_factory=dict)

    def put(self, trigger: WebhookTrigger) -> None:
        self.records[trigger.name] = trigger

    def get(self, name: str) -> Optional[WebhookTrigger]:
        return self.records.get(name)

    def delete(self, name: str) -> bool:
        return self.records.pop(name, None) is not None

    def list(self) -> List[WebhookTrigger]:
        return list(self.records.values())


@dataclass(init=False)
class WebhookRegistry:
    store: WebhookStore

    def __init__(
        self,
        triggers: Optional[Dict[str, WebhookTrigger]] = None,
        *,
        store: Optional[WebhookStore] = None,
    ) -> None:
        """Accept the legacy mapping while allowing a workflow-owned store."""
        self.store = store or InMemoryWebhookStore()
        for trigger in (triggers or {}).values():
            self.store.put(trigger)

    @property
    def triggers(self) -> Dict[str, WebhookTrigger]:
        """Legacy mapping view retained for current callers."""
        records = getattr(self.store, "records", None)
        if records is None:
            return {trigger.name: trigger for trigger in self.store.list()}
        return records

    def register(
        self,
        name: str,
        yaml_definition: str,
        description: str = "",
        *,
        secret: Optional[str] = None,
    ) -> WebhookTrigger:
        trigger = WebhookTrigger(name, yaml_definition, description, secret)
        self.store.put(trigger)
        return trigger

    def get(self, name: str) -> Optional[WebhookTrigger]:
        return self.store.get(name)

    def unregister(self, name: str) -> bool:
        return self.store.delete(name)

    def list_triggers(self) -> List[Dict]:
        return [
            {"name": t.name, "description": t.description} for t in self.store.list()
        ]

    def verify_signature(
        self, name: str, body: bytes, signature: Optional[str]
    ) -> bool:
        """Verify HMAC only for registrations that explicitly configured a secret."""
        trigger = self.get(name)
        if trigger is None:
            return False
        if not trigger.secret:
            return True
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(
            trigger.secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature[7:], expected)
