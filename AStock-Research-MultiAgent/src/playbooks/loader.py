"""Load and index YAML playbooks with strict schema validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.domain.models import TaskType
from src.playbooks.models import PlaybookDefinition


def load_playbook(path: str | Path) -> PlaybookDefinition:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"playbook {source} must contain a YAML mapping")
    return PlaybookDefinition.model_validate(payload)


class PlaybookRegistry:
    def __init__(self) -> None:
        self._playbooks: dict[str, PlaybookDefinition] = {}

    def register(self, playbook: PlaybookDefinition) -> None:
        if playbook.playbook_id in self._playbooks:
            raise ValueError(f"duplicate playbook_id: {playbook.playbook_id}")
        self._playbooks[playbook.playbook_id] = playbook

    def load_directory(self, directory: str | Path) -> None:
        for path in sorted(Path(directory).glob("*.yaml")):
            self.register(load_playbook(path))

    def get(self, playbook_id: str) -> PlaybookDefinition:
        try:
            return self._playbooks[playbook_id]
        except KeyError as error:
            raise KeyError(f"unknown playbook: {playbook_id}") from error

    def select_for(self, task_type: TaskType) -> list[PlaybookDefinition]:
        return [
            playbook
            for playbook in self._playbooks.values()
            if task_type in playbook.task_types
        ]

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._playbooks))
