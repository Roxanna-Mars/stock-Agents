"""Validated schema for reusable research procedures."""

from __future__ import annotations

from pydantic import Field, model_validator

from src.domain.models import StrictModel, TaskType


class PlaybookDataRequirement(StrictModel):
    data_type: str = Field(min_length=1)
    required_fields: list[str] = Field(default_factory=list)
    provider_preferences: list[str] = Field(default_factory=list)
    required: bool = True


class PlaybookDefinition(StrictModel):
    playbook_id: str = Field(min_length=1)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    task_types: list[TaskType] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    data_requirements: list[PlaybookDataRequirement] = Field(default_factory=list)
    compute_operators: list[str] = Field(default_factory=list)
    output_sections: list[str] = Field(min_length=1)
    quality_gates: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_items(self) -> "PlaybookDefinition":
        for field_name in (
            "roles",
            "compute_operators",
            "output_sections",
            "quality_gates",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates")
        return self
