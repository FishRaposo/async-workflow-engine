"""Deterministic YAML version hashes for reproducible reruns."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Optional

import yaml

from .parser import WorkflowValidationError


def canonical_yaml_hash(yaml_definition: str) -> str:
    """Hash YAML data, not incidental key ordering or whitespace."""
    try:
        parsed = yaml.safe_load(yaml_definition)
    except yaml.YAMLError as exc:
        raise WorkflowValidationError(f"Invalid YAML: {exc}") from exc
    canonical = yaml.safe_dump(
        parsed, sort_keys=True, default_flow_style=False, allow_unicode=True
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkflowVersion:
    content_hash: str
    yaml_definition: str


class WorkflowVersionStore:
    def put(self, yaml_definition: str) -> WorkflowVersion: ...

    def get(self, content_hash: str) -> Optional[WorkflowVersion]: ...


class InMemoryWorkflowVersionStore(WorkflowVersionStore):
    def __init__(self) -> None:
        self._versions: Dict[str, WorkflowVersion] = {}

    def put(self, yaml_definition: str) -> WorkflowVersion:
        content_hash = canonical_yaml_hash(yaml_definition)
        return self._versions.setdefault(
            content_hash, WorkflowVersion(content_hash, yaml_definition)
        )

    def get(self, content_hash: str) -> Optional[WorkflowVersion]:
        return self._versions.get(content_hash)
