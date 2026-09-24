"""Pydantic models for the tracker endpoints (docs/api-contract.md).

Cell values are typed ``Any`` at the boundary on purpose: the authoritative
validation is the dynamic per-column schema in ``domain.operations``
(brief 4.3), not these transport models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class OperationsBody(BaseModel):
    """Wire rule: unknown fields rejected, no type coercion (see StrictModel)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    base_revision: int
    operations: list[dict[str, Any]]


class OperationsResult(BaseModel):
    revision: int
    applied: list[dict[str, Any]]


class SelectOptionModel(BaseModel):
    key: str
    label: str
    color: str | None = None


class ColumnDefinitionModel(BaseModel):
    key: str
    type: str
    label: str
    system: bool = False
    options: list[SelectOptionModel] | None = None
    currency: str | None = None
    max: int | None = None
    computed: str | None = None
    width: int | None = None


class TrackerDefinitionModel(BaseModel):
    template_key: str
    template_version: int
    revision: int
    columns: list[ColumnDefinitionModel]
    conditional_rules: list[dict[str, Any]]
    settings: dict[str, Any]


class TrackerRowModel(BaseModel):
    id: str
    order_key: str
    cells: dict[str, Any]


class TrackerPayload(BaseModel):
    definition: TrackerDefinitionModel
    rows: list[TrackerRowModel]
