"""Pydantic models for the project endpoints (docs/api-contract.md)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Wire rule: unknown fields rejected, no type coercion. ``strict``
    means "5" stays a string and fails validation instead of becoming 5."""

    model_config = ConfigDict(extra="forbid", strict=True)


class ProjectCreate(StrictModel):
    template_key: str
    name: str = Field(min_length=1)
    description: str | None = None
    settings: dict[str, Any] = {}


class ProjectUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    archived: bool | None = None


class DocumentTypeRead(BaseModel):
    """One entry of the template's document-type list (us-4 item 1): the
    upload form offers exactly these keys, and the flag drives the consent
    and eligibility rules."""

    key: str
    label: str
    model_eligible: bool


class ProjectRead(BaseModel):
    """Project as returned on the wire."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    template_key: str
    template_version: int
    archived: bool
    document_types: list[DocumentTypeRead]
    created_at: str
    updated_at: str


class ProjectList(BaseModel):
    data: list[ProjectRead]
